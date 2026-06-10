---
tags:
  - '#research'
  - '#graph-backend'
date: '2026-06-10'
related:
  - '[[2026-03-22-graph-hardening-research]]'
---

# `graph-backend` research: `hardened graph backend for gui visualisation`

Research into hardening the vault document graph into the technical backend for a
future GUI graph-visualisation frontend. The brief asks for per-feature and
per-connection corpus visualisation, Obsidian-graph-canvas-like connection strengths
and semantic linking (the brief's "NERD connection interface"), and graph-manipulation
CRUD CLI verbs. Three research threads ran in parallel: a codebase readiness audit of
the existing graph stack, a design-space survey of connection-strength and semantic
linking, and a survey of CLI-as-GUI-backend interface patterns. The prior
graph-hardening feature (March 2026) already delivered phantom nodes, the dangling
checker, and 68 tests; this research scopes what remains between that baseline and a
production GUI backend.

## Findings

### Current state: the graph is structurally mature but GUI-blind

`src/vaultspec_core/graph/api.py` builds a `networkx.DiGraph` over `.vault/` in three
passes: node creation with stem-collision qualification, link resolution (body
wiki-links plus `related:` frontmatter) with phantom materialisation for unresolved
targets and archive-aware resolution, and attribute sync. Query surface covers feature
scoping, orphans, dangling pairs, rankings, and subgraph views. Rendering covers Rich
tree, phart ASCII, and node-link JSON wrapped in the standard envelope
(`vaultspec.vault.graph.v1`). 68 tests in `src/vaultspec_core/graph/tests/test_graph.py`
run against a deterministic 120-document synthetic corpus with seeded pathologies
(cycles, orphans, stem collisions, phantom-only links) - no mocks.

What is missing for a GUI consumer, in order of severity:

- **Edges carry zero attributes.** Both `add_edge` call sites pass no `weight`, no
  `kind`, no provenance. A GUI cannot distinguish a `related:` frontmatter edge from a
  body wiki-link, cannot size edges, and cannot answer "why are these connected".
  Link extraction in `src/vaultspec_core/vaultcore/links.py` returns a `set`, so
  multiplicity (a doc referencing another five times) is discarded at the source.
- **No caching or incremental updates.** Every CLI invocation, MCP `find` call, and
  check command constructs `VaultGraph` from scratch: full `scan_vault`, full-file
  read/parse, full link resolution. Some commands build the graph twice
  (`vaultcore/query.py` stats path). Full body text is retained in memory on every
  node regardless of output flags. `metrics()` unconditionally runs
  `nx.betweenness_centrality` (O(V\*E)) and is invoked twice on the `--json` path
  (`to_dict` calls it after the CLI already has). Proven operating point is ~440
  nodes; estimated 5-15 s builds at 5,000 docs, unusable at 50,000.
- **Machine-contract instability (sharp finding).** `node_link_data(g)` is called with
  no `edges=` argument while `pyproject.toml` pins `networkx>=3.4` unbounded. networkx
  3.4/3.5 emit the `links` key by default; 3.6 flipped the default to `edges`. The
  shipped contract and the test asserting `"edges"` are correct only because 3.6.1
  happens to resolve. A clean install resolving 3.4/3.5 silently breaks every JSON
  consumer. Fix: pass `edges="edges"` explicitly and/or raise the floor to
  `networkx>=3.6`.
- **No graph-mutation verbs.** The only edge mutator in the codebase is
  `vault check dangling --fix`, which removes dead `related:` entries via targeted
  line surgery (CRLF-preserving, atomic). There is no verb to add or list edges.
- **No stable node identity.** Node keys are filename stems (doc-type-qualified on
  collision); a rename invalidates any GUI-side state. No content hash or UUID.
- **Contract coverage gaps.** No test asserts the full JSON envelope shape, the
  archive-resolution branch, feature-scoped centrality, or any behaviour above 120
  docs. `avg_in_degree` and `avg_out_degree` are duplicates by construction.
- **MCP does not expose the graph.** `src/vaultspec_core/mcp_server/` registers only
  `find` and `create` over stdio; `VaultGraph` is used internally for ranking only.

### Connection strengths and semantic linking: the design space

Obsidian's core graph view is structural and unweighted: nodes are notes, node size is
in-degree, unresolved links render as "not created" nodes (the existing phantom model
is already at parity), groups are search-query-driven colouring, and physics/layout are
purely client-side. Per-edge connection strength is not an Obsidian-core concept - it
is what the Graph Analysis plugin adds, via Jaccard similarity, Adamic-Adar, common
neighbours, co-citation, label propagation, and clustering coefficient. Every one of
those algorithms ships in the already-pinned `networkx` dependency (link-prediction
family on an undirected projection, community detection, `nx.ego_graph` for Obsidian's
local-graph depth slider, `nx.pagerank` for node importance). Foam, Dendron, and
Logseq are likewise purely structural. The consensus across the product category:
computed relatedness is graph-structural; embeddings and entity extraction are not
standard anywhere.

Candidate signals ranked by cost/benefit for this codebase:

- **Zero new dependencies, deterministic, Windows-clean (stage 1 material):** explicit
  link multiplicity (requires `links.py` to return counts), reciprocity, shared
  feature tag, shared non-feature tags (directory tags must be excluded or
  IDF-down-weighted or everything connects to everything), co-citation/bibliographic
  coupling via networkx link-prediction on `g.to_undirected()`, pagerank node sizing.
  All testable with exact-value assertions on the synthetic corpus, satisfying the
  no-mock mandate.
- **Zero-dependency but own-the-math (stage 1 optional / stage 2 floor):** pure-Python
  TF-IDF cosine with an inverted index and top-k capping; deterministic with a fixed
  tokenizer; borderline at 5,000 docs without candidate pruning.
- **Heavy and non-deterministic (stage 2, opt-in extra only):** scikit-learn TF-IDF/BM25
  (numpy+scipy burden), sentence-transformer or ONNX embeddings (hundreds of MB,
  float-level non-determinism that collides with the assert-real-outputs testing
  mandate; needs tolerance-based ranking assertions behind the `integration` marker).
- **Lowest ROI for this corpus (defer pending user confirmation):** literal named-entity
  recognition and disambiguation. Vault documents are short, internally
  cross-referenced spec artifacts whose salient entities are feature tags, document
  stems, and plan identifiers - all already explicit structure. Generic NER would
  mostly rediscover the feature taxonomy at the highest dependency and test cost.

**Open question carried to the ADR gate:** the brief's term "NERD connection
interface" appears nowhere in the repository. The plausible NLP reading (named entity
recognition and disambiguation) is the costliest, least-fitting branch above. This
research interprets "semantic linking with connection strengths" as structural
weighting plus optional text similarity, matching every precedent tool; the
interpretation needs explicit user confirmation before the ADR commits to it.

Recommended edge data model: keep the explicit `DiGraph` as the source of truth
(direction, dangling detection, phantoms all depend on edge = real reference); attach
`weight`, `kind` (provenance enum: explicit, reciprocal, shared-feature, shared-tag,
co-citation, semantic), `multiplicity`, and a raw `signals` map to explicit edges; emit
derived/implicit relatedness edges as a separate parallel edge set rather than
polluting the canonical graph, so orphan/dangling semantics stay intact and a GUI (and
tests) can always answer why an edge exists. Composition into a single blended score,
if offered, must be a documented linear combination with version-pinned coefficients so
tests can assert exact arithmetic.

### CLI-as-GUI-backend interface patterns

Established conventions the new surface must follow: the `json_envelope` helper in
`src/vaultspec_core/cli/rendering.py` (`{schema, status, data, hints?}` with
`vaultspec.<command>.v1` schema strings and a separate `vaultspec.error.v1` envelope),
the sync vocabulary, exit codes 0/1, mandatory `--dry-run` on every mutating verb,
`--feature`/`-f` scoping, `--target`/`-t`, and post-edit `vaultspec-core sync` to
propagate the bundled CLI reference.

Transport recommendation is a staged path, validated by precedent (Dendron's engine
server and Foam both started synchronous and added the daemon only when interactivity
demanded it; git GUIs drive stable plumbing; jujutsu integrates at the library
boundary, and `VaultGraph` is already an importable library):

- **Stage 0:** GUI shells out to `vault graph --json` and re-fetches after mutations.
  Already works; needs the contract pinned and tested first.
- **Stage 1:** edge-CRUD verbs land so the GUI mutates through the CLI; still one-shot.
- **Stage 2 (deferred until measured):** fingerprint-keyed graph cache for one-shot
  calls, and/or a `vault serve` HTTP+SSE daemon holding a warm graph and pushing
  deltas. `starlette`, `uvicorn`, `sse-starlette`, and `httpx` are already declared
  dependencies (currently unused first-party, transitive from the MCP SDK), so the
  daemon adds no new dependency weight. The MCP server is the wrong vehicle for graph
  streaming (stdio-only, tool-shaped, per-call context isolation rebuilds the graph
  anyway).

Graph CRUD on a derived graph decomposes cleanly: node create is `vault add`, node
retire is `vault feature archive`/`unarchive` (existing discipline), and edge CRUD
means safe programmatic mutation of `related:` frontmatter only. Proposed verb shape
consistent with the existing grammar: `vault link add <src> <dst>`,
`vault link remove <src> <dst>`, `vault link list [<src>]`, each with `--dry-run` and
`--json`. Invariants: mutate only the `related:` block via the proven line-surgery
approach in `vaultcore/checks/dangling.py` (CRLF-preserving, atomic, quoted
wiki-links - never a whole-document YAML round-trip); body wiki-links remain a
read-only edge source (content authoring, not graph manipulation - mirrors the plan
structure-vs-prose split); `add` refuses or warns on creating a dangling edge; reuse
`resolve_related_inputs` from `vaultcore.resolve` for target resolution.

Layout belongs in the frontend. No positions are computed today; shipping volatile
coordinates would destabilise the contract. The backend ships topology plus layout
inputs (degree, centrality, pagerank, weights) and leaves force simulation to the
client. Deterministic server-side layout, if ever needed for static export, goes
behind an explicit flag.

Caching primitive already exists: the repair pipeline fingerprints files as
`(st_size, st_mtime_ns)` in `vaultcore/repair.py`. An mtime/size manifest beside a
serialised graph cache captures most of the rescan win for far less code than true
incremental rebuild; defer in-process warm caching to the daemon stage.

### Synthesis: shape of the work

The hardening decomposes into four concerns, in dependency order:

- **Contract hardening (foundation):** pin the node-link `edges=` key and the networkx
  floor; add a contract test asserting the full `vaultspec.vault.graph.v1` envelope;
  fix the double `metrics()` computation; close the test gaps (archive resolution,
  feature-scoped centrality, envelope shape); decide schema v2 fields (edge attrs,
  node-size hints) once, bump once.
- **Weighted edges (stage 1, zero new dependencies):** preserve link multiplicity in
  the extractor; attach `kind`/`weight`/`multiplicity` to explicit edges; add the
  parallel derived-edge set (reciprocity, shared tags, co-citation family via
  networkx); pagerank node-size hints; ego-graph depth scoping for local-graph parity;
  expose via schema v2.
- **Edge CRUD verbs:** `vault link add/remove/list` with dry-run, JSON envelopes,
  frontmatter line surgery, dangling-edge refusal.
- **Performance (measured, not speculative):** fingerprint cache around graph
  construction; scale benchmarks into the test suite at marked tiers; the serve
  daemon and SSE deltas only when one-shot latency is measured as the GUI bottleneck.
  Optional semantic similarity (TF-IDF floor, embeddings ceiling) goes behind a
  `[semantic]` extra in a later phase, pending the NERD-interpretation confirmation.
