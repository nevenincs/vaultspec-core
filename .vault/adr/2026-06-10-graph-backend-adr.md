---
tags:
  - '#adr'
  - '#graph-backend'
date: '2026-06-10'
modified: '2026-06-10'
related:
  - '[[2026-06-10-graph-backend-research]]'
---

# `graph-backend` adr: `gui graph backend hardening` | (**status:** `accepted`)

## Problem Statement

The vault document graph (`src/vaultspec_core/graph/api.py`) was built as a local CLI
convenience and hardened once (phantom nodes, dangling checker, 68 tests) but was never
specified as a machine-facing backend. It is now explicitly targeted as the technical
backend for a future GUI frontend that needs Obsidian-graph-canvas-like visualisation:
per-feature and per-connection corpus views, connection strengths, semantic linking,
and graph-manipulation CRUD through the CLI. The research found four blocking gaps:
edges carry zero attributes (no weight, kind, or provenance), the JSON wire contract is
unstable (the node-link `edges` key depends on which networkx version resolves), there
are no graph-mutation verbs, and every invocation re-parses the whole vault with no
caching. This ADR fixes the architecture for closing those gaps.

## Considerations

- The prior graph-hardening decisions hold and are built upon: phantom nodes as
  first-class citizens, dangling links as ERROR-severity diagnostics, snapshot
  exclusion of phantoms. Nothing here reverses them.
- Obsidian core's graph view is structural and unweighted; per-edge strength is a
  plugin concept (Graph Analysis: Jaccard, Adamic-Adar, co-citation, common
  neighbours, label propagation). Every one of those algorithms ships in the
  already-pinned `networkx` dependency. Foam, Dendron, and Logseq are likewise
  structural. No precedent tool in the category uses embeddings or entity extraction
  as its primary relatedness signal.
- The brief's term "NERD connection interface" appears nowhere in the repository; the
  user confirmed at the ADR gate that the term was a speech-to-text transcription
  artifact. The requirement stands as connection-strength weighting plus semantic
  linking, which this ADR delivers as structural weighting now and optional
  text-similarity edges in a follow-on, matching every precedent tool. A literal
  named-entity reading was researched anyway and assessed lowest-ROI for this corpus:
  vault documents are short spec artifacts whose salient entities (feature tags,
  document stems, plan identifiers) are already explicit structure.
- A GUI consumer needs: typed weighted edges, node-size hints, local-graph (ego)
  scoping, a versioned stable JSON contract, mutation verbs it can call, and
  eventually sub-second refresh. It does not need server-computed layout: force
  simulation belongs client-side, and volatile coordinates would destabilise the
  contract.
- Transport precedents (Dendron engine server, Foam, git GUIs, jujutsu's library-first
  integration) all validate a staged path: one-shot JSON first, daemon only when
  interactivity demands it. `starlette`, `uvicorn`, `sse-starlette`, and `httpx` are
  already declared dependencies, so a future serve mode adds no dependency weight.
- The testing mandate (no mocks, assert real outputs) admits structural weighting
  trivially (exact counts, exact networkx scores on the deterministic synthetic
  corpus) but collides with float-level non-determinism of embeddings; semantic
  similarity therefore cannot live in the default install or default test tier.

## Constraints

- `networkx>=3.4` is currently unbounded and the node-link serialisation default
  changed at 3.6 (`links` became `edges`). The wire contract is only accidentally
  correct today. Any contract work must first pin the key explicitly and raise the
  floor; this is a parent-feature stability issue for everything else in this ADR.
- Edge mutation must never round-trip whole documents through a YAML dumper. The
  proven approach is the targeted line surgery in `vaultcore/checks/dangling.py`
  (CRLF-preserving, atomic writes, quoted wiki-links). New verbs reuse it.
- Body wiki-links are content, not structure. Graph CRUD may mutate only `related:`
  frontmatter; prose edges remain read-only signals (mirrors the plan
  structure-via-CLI, prose-by-hand discipline).
- Derived relatedness edges must not enter the canonical DiGraph: orphan detection,
  dangling diagnostics, and checker semantics all assume edge = real authored
  reference. Pollution would corrupt `vault check` results.
- Node keys are filename stems; renames invalidate GUI-side state. Stable node
  identity (content hash or UUID) is acknowledged but out of scope here; the GUI must
  treat node ids as rename-fragile until a future ADR addresses identity.
- Scale envelope: proven at ~440 nodes; the design targets correct behaviour to ~5,000
  documents with the fingerprint cache, and explicitly does not target 50,000 in this
  feature.

## Implementation

Four layers, in dependency order.

**Layer 1 - contract hardening.** Call `node_link_data` with an explicit
`edges="edges"` argument and raise the dependency floor to `networkx>=3.6`. Fix the
double `metrics()` computation on the JSON path. Bump the graph envelope schema from
`vaultspec.vault.graph.v1` to `vaultspec.vault.graph.v2` exactly once, carrying all
layer 2 additions, and add a contract test that asserts the full envelope shape
(schema string, status, every node field, every edge field, metrics keys) against the
synthetic corpus. Close the known test gaps: archive-resolution branch, feature-scoped
centrality, collision fan-out assertion.

**Layer 2 - weighted typed edges.** Link extraction in `vaultcore/links.py` preserves
multiplicity (counts per target) instead of collapsing to a set. Explicit edges on the
canonical DiGraph gain attributes: `kind` (provenance: `related` frontmatter vs `body`
wiki-link), `multiplicity`, and a normalised `weight`. A parallel derived-edge set -
computed on demand, never stored in the canonical DiGraph - carries implicit
relatedness: reciprocity, shared feature tag, shared non-feature tags (directory tags
excluded), and the networkx link-prediction family (Jaccard coefficient, Adamic-Adar,
co-citation) on an undirected projection. Each derived edge carries `kind`, a raw
`signals` map, and a composed `weight` defined as a documented linear combination with
version-pinned coefficients. Node-size hints (`pagerank`, in-degree) become node
attributes. `vault graph` gains `--node <stem> --depth N` ego-graph scoping for
Obsidian local-graph parity, and a flag to include or exclude the derived edge set.

**Layer 3 - edge CRUD verbs.** New `vault link` command group: `vault link add <src> <dst>`, `vault link remove <src> <dst>`, `vault link list [<src>]`, each with
`--dry-run`, `--json` (schemas `vaultspec.vault.link.<verb>.v1`), and exit codes 0/1.
`add` resolves targets via `vaultcore.resolve` and refuses to create a dangling edge
without `--force`; `remove` reuses the dangling-fix line surgery; `list` reads
`in_links`/`out_links` off the built graph. All mutation touches only the `related:`
frontmatter block.

**Layer 4 - performance, measured.** A fingerprint cache keyed on
`(st_size, st_mtime_ns)` per file (the primitive already used by the repair pipeline)
wraps graph construction: when no fingerprint changed, the graph loads from a
serialised cache instead of re-parsing the corpus. Scale benchmarks (500 and 5,000
synthetic documents) enter the test suite under a dedicated marker with generous
thresholds. The serve daemon (HTTP + SSE pushing deltas from a warm graph) and the
optional `[semantic]` extra (TF-IDF floor, embeddings ceiling) are explicitly deferred
to follow-on features: the daemon until one-shot latency is measured as the GUI
bottleneck, the semantic extra until structural weighting has shipped and its
relatedness quality can be judged against real GUI usage.

## Rationale

The research established that ~90% of the requested Obsidian-like capability
(connection strengths, relatedness panels, local graph, node sizing) is achievable
with zero new dependencies, full determinism, and exact-value tests - because the
algorithms live in the networkx dependency the project already ships. Choosing
structural weighting first and gating semantic similarity behind an optional extra
keeps the core install small, keeps the no-mock testing mandate satisfiable, and
isolates Windows-wheel and non-determinism risk. Keeping derived edges out of the
canonical DiGraph preserves the correctness of every existing checker. Contract
pinning comes first because every downstream consumer - GUI, tests, MCP - inherits its
stability; the schema bumps once to v2 rather than churning per layer. Edge CRUD as
`related:`-only mutation follows the established split between structure (CLI-owned)
and prose (author-owned), and reuses write paths that already survived an audit cycle.

## Consequences

- The GUI gets a stable, versioned, typed wire contract; the CLI gets `vault link`
  verbs; checkers and existing consumers are untouched because derived edges stay out
  of the canonical graph.
- The graph envelope moves to `vaultspec.vault.graph.v2` with no compatibility mode:
  the user confirmed at the ADR gate that no v1 consumers exist to maintain, so the
  bump is free and no migration shims are written.
- The networkx floor rises to 3.6, dropping environments that resolved 3.4/3.5 -
  accepted, since those environments were emitting a different wire key anyway.
- Link-extraction multiplicity changes a long-standing return type in
  `vaultcore/links.py`; all call sites (graph build, checkers) must be audited in the
  plan.
- The fingerprint cache introduces a cache-invalidation surface; every mutating verb
  must invalidate or refresh it, and a stale cache must never be silently trusted (a
  fingerprint mismatch always falls back to full rebuild).
- Deferred items create explicit follow-on work: serve daemon, semantic extra, stable
  node identity. Each needs its own ADR; this ADR's scope ends at one-shot CLI parity.
- The derived-edge model is open to future signal sources (text similarity, entity
  extraction) as new `kind` values without rework; only the signal computation would
  be new code.

## Codification candidates

- **Rule slug:** `json-schema-version-discipline`.
  **Rule:** Any change to the shape of a `vaultspec.*` `--json` payload must bump the
  schema version suffix and ship with a contract test asserting the full envelope
  shape in the same change.

- **Rule slug:** `derived-edges-stay-out-of-canonical-graph`.
  **Rule:** Computed relatedness edges (weights, similarity, entity links) must never
  be inserted into the canonical document DiGraph consumed by checkers; they live in a
  parallel derived edge set with explicit provenance.
