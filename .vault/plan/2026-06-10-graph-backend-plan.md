---
tags:
  - '#plan'
  - '#graph-backend'
date: '2026-06-10'
tier: L2
related:
  - '[[2026-06-10-graph-backend-adr]]'
  - '[[2026-06-10-graph-backend-research]]'
---

# `graph-backend` plan

## Description

Harden the vault document graph into the specified technical backend for a future GUI
graph-visualisation frontend, per the accepted gui-graph-backend-hardening ADR and the
graph-backend research. Four phases in dependency order: P01 pins the JSON wire
contract (explicit node-link edges key, networkx 3.6 floor, single metrics pass, one
schema bump to v2 with a full contract test) because every downstream consumer
inherits its stability; P02 delivers connection strengths with zero new dependencies
by typing and weighting explicit edges (kind, multiplicity, weight), computing a
parallel derived relatedness edge set (reciprocity, shared tags, jaccard, adamic-adar,
co-citation via networkx) that never enters the checker-facing graph, plus pagerank
node-size hints and ego-graph local scoping for Obsidian-style local-graph parity; P03
adds the vault link command group (add, remove, list) mutating only related
frontmatter through CRLF-preserving atomic line surgery; P04 adds the
fingerprint-keyed graph cache (stale never trusted, mismatch falls back to full
rebuild) and scale benchmarks. The serve daemon, semantic-similarity extra, and stable
node identity are explicitly out of scope as decided in the ADR.

## Steps

### Phase `P01` - contract hardening

Pin the graph JSON wire contract, fix wasteful metrics computation, and close known coverage gaps so every downstream consumer inherits a stable v2 envelope.

- [x] `P01.S01` - pass an explicit edges keyword to the node-link serialisation call so the wire key is version-independent; `src/vaultspec_core/graph/api.py`.
- [x] `P01.S02` - raise the networkx dependency floor to 3.6; `pyproject.toml`.
- [x] `P01.S03` - eliminate the duplicate metrics computation on the JSON export path; `src/vaultspec_core/graph/api.py`.
- [x] `P01.S04` - bump the graph envelope schema to vaultspec.vault.graph.v2; `src/vaultspec_core/cli/vault_cmd.py`.
- [x] `P01.S05` - add a full-envelope v2 contract test asserting schema, status, every node field, every edge field, and metrics keys; `src/vaultspec_core/graph/tests/test_contract.py`.
- [x] `P01.S06` - add archive-resolution branch tests covering link resolution against the archive directory; `src/vaultspec_core/graph/tests/test_graph.py`.
- [x] `P01.S07` - add feature-scoped centrality assertions and replace the early-returning collision fan-out test with a guaranteed assertion; `src/vaultspec_core/graph/tests/test_graph.py`.

### Phase `P02` - weighted typed edges

Deliver connection strengths with zero new dependencies: provenance-typed weighted explicit edges, a parallel derived relatedness edge set, node-size hints, and local-graph scoping, all exposed through the v2 payload.

- [x] `P02.S08` - preserve wiki-link and related-link multiplicity by returning per-target counts from the extractors; `src/vaultspec_core/vaultcore/links.py`.
- [x] `P02.S09` - audit and update every extractor call site for the counted return shape; `src/vaultspec_core/vaultcore/`.
- [x] `P02.S10` - attach kind, multiplicity, and normalised weight attributes to explicit edges during graph build; `src/vaultspec_core/graph/api.py`.
- [x] `P02.S11` - create the derived relatedness edge module computing reciprocity, shared-tag, jaccard, adamic-adar, and co-citation signals with documented composition coefficients; `src/vaultspec_core/graph/derived.py`.
- [x] `P02.S12` - add pagerank and in-degree node-size hints as node attributes; `src/vaultspec_core/graph/api.py`.
- [x] `P02.S13` - add ego-graph local scoping by node and depth to the graph query surface; `src/vaultspec_core/graph/api.py`.
- [x] `P02.S14` - emit explicit edge attributes and the derived edge set in the v2 JSON payload; `src/vaultspec_core/graph/api.py`.
- [x] `P02.S15` - add node, depth, and derived-edge toggles to the vault graph verb; `src/vaultspec_core/cli/vault_cmd.py`.
- [x] `P02.S16` - add exact-value tests for multiplicity, edge attributes, and normalised weights on the synthetic corpus; `src/vaultspec_core/graph/tests/test_graph.py`.
- [x] `P02.S17` - add exact-value tests for every derived signal and the composed weight; `src/vaultspec_core/graph/tests/test_derived.py`.
- [x] `P02.S18` - add CLI tests for ego scoping and derived-edge toggles; `src/vaultspec_core/tests/cli/test_vault_cli.py`.
- [x] `P02.S19` - regenerate the bundled CLI reference and propagate provider sync; `.vaultspec/rules/reference/cli.md`.

### Phase `P03` - vault link crud verbs

Add the vault link command group so a GUI can mutate graph edges through the CLI by safe related-frontmatter surgery only.

- [x] `P03.S20` - extract the related-frontmatter line surgery from the dangling fixer into a shared CRLF-preserving atomic helper; `src/vaultspec_core/vaultcore/`.
- [x] `P03.S21` - create the vault link command group with the list verb and versioned JSON envelopes; `src/vaultspec_core/cli/link_cmd.py`.
- [ ] `P03.S22` - implement vault link add with target resolution, dangling refusal behind force, and dry-run preview; `src/vaultspec_core/cli/link_cmd.py`.
- [ ] `P03.S23` - implement vault link remove reusing the shared related-entry surgery with dry-run preview; `src/vaultspec_core/cli/link_cmd.py`.
- [ ] `P03.S24` - register the link group on the vault command app and wire the exit-code contract; `src/vaultspec_core/cli/vault_cmd.py`.
- [ ] `P03.S25` - add CRLF-preservation, atomic-write, and round-trip tests for the shared surgery helper; `src/vaultspec_core/vaultcore/tests/test_link_surgery.py`.
- [ ] `P03.S26` - add CLI tests for link add, remove, and list covering dry-run, JSON envelopes, dangling refusal, and exit codes; `src/vaultspec_core/tests/cli/test_link_cli.py`.
- [ ] `P03.S27` - regenerate the bundled CLI reference and propagate provider sync; `.vaultspec/rules/reference/cli.md`.

### Phase `P04` - performance and caching

Add the fingerprint graph cache and scale benchmarks so repeated one-shot reads stop re-parsing the whole corpus.

- [ ] `P04.S28` - create the fingerprint cache module with a size and mtime manifest and a serialised graph store; `src/vaultspec_core/graph/cache.py`.
- [ ] `P04.S29` - wire cache loading into graph construction with any fingerprint mismatch falling back to full rebuild; `src/vaultspec_core/graph/api.py`.
- [ ] `P04.S30` - invalidate or refresh the graph cache from every mutating verb that touches vault documents; `src/vaultspec_core/cli/`.
- [ ] `P04.S31` - add cache correctness tests proving a stale cache is never trusted; `src/vaultspec_core/graph/tests/test_cache.py`.
- [ ] `P04.S32` - add 500 and 5000 document scale benchmarks with generous thresholds; `src/vaultspec_core/graph/tests/test_scale.py`.
- [ ] `P04.S33` - register the dedicated benchmark marker; `pyproject.toml`.

## Parallelization

Phases are sequenced: P01 must land before P02 (the v2 schema bump carries the edge
attributes P02 emits), and P02 before P03 only for the shared graph test fixtures;
P03 is otherwise independent of P02 and may start once P01 lands. P04 depends on P01
and P02 (the cache serialises the attributed graph) and on P03 for the invalidation
hooks of the link verbs. Within phases: P01 steps S01 to S04 are sequential (same
file region), S05 to S07 parallelize after S04. P02 steps S08 and S09 land together
first; S10 to S14 are sequential on the graph module; S15 follows S14; tests S16 to
S18 parallelize after their subjects. P03 step S20 precedes S22 and S23; S21 may
start immediately; tests S25 and S26 parallelize after implementation. P04 is
sequential through S30, then S31 to S33 parallelize. Implementation steps go to
sonnet-tier executor subagents, with opus-tier reserved for P02 S10 to S14 (graph
build internals) and P04 S29 (cache wiring), per the orchestration brief.

## Verification

- The full test suite passes with zero skips, mocks, or tautological assertions; new
  tests assert exact real values on the deterministic synthetic corpus.
- The v2 contract test asserts the complete envelope shape and fails if any field is
  added, removed, or renamed without a schema bump.
- A clean-environment install resolving the new networkx floor emits the identical
  node-link edges key as the development environment.
- Every new or changed verb (vault graph toggles, vault link add, remove, list)
  accepts dry-run where mutating, emits versioned JSON envelopes, honours the 0/1
  exit-code contract, and appears in the regenerated bundled CLI reference after
  provider sync.
- vault link add refuses to create a dangling edge without force; vault link remove
  preserves CRLF line endings and document bytes outside the related block.
- Cache correctness: any fingerprint mismatch triggers full rebuild; no test or
  manual probe can elicit stale graph data from the cache.
- Scale benchmarks at 500 and 5000 synthetic documents complete within their declared
  thresholds under the dedicated marker.
- vault check all stays green and vaultspec-core spec doctor reports a healthy
  workspace after every phase.
- Code review via the vaultspec-code-review skill signs off each phase before the
  next begins; the plan is complete when every Step row is closed.
