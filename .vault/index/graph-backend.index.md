---
generated: true
tags:
  - '#index'
  - '#graph-backend'
date: '2026-06-10'
related:
  - '[[2026-06-10-graph-backend-P01-S01]]'
  - '[[2026-06-10-graph-backend-P01-S02]]'
  - '[[2026-06-10-graph-backend-P01-S03]]'
  - '[[2026-06-10-graph-backend-P01-S04]]'
  - '[[2026-06-10-graph-backend-P01-S05]]'
  - '[[2026-06-10-graph-backend-P01-S06]]'
  - '[[2026-06-10-graph-backend-P01-S07]]'
  - '[[2026-06-10-graph-backend-P01-summary]]'
  - '[[2026-06-10-graph-backend-P02-S08]]'
  - '[[2026-06-10-graph-backend-P02-S09]]'
  - '[[2026-06-10-graph-backend-P02-S10]]'
  - '[[2026-06-10-graph-backend-P02-S11]]'
  - '[[2026-06-10-graph-backend-P02-S12]]'
  - '[[2026-06-10-graph-backend-P02-S13]]'
  - '[[2026-06-10-graph-backend-P02-S14]]'
  - '[[2026-06-10-graph-backend-P02-S15]]'
  - '[[2026-06-10-graph-backend-P02-S16]]'
  - '[[2026-06-10-graph-backend-P02-S17]]'
  - '[[2026-06-10-graph-backend-P02-S18]]'
  - '[[2026-06-10-graph-backend-P02-S19]]'
  - '[[2026-06-10-graph-backend-P02-summary]]'
  - '[[2026-06-10-graph-backend-P03-S20]]'
  - '[[2026-06-10-graph-backend-P03-S21]]'
  - '[[2026-06-10-graph-backend-P03-S22]]'
  - '[[2026-06-10-graph-backend-P03-S23]]'
  - '[[2026-06-10-graph-backend-P03-S24]]'
  - '[[2026-06-10-graph-backend-P03-S25]]'
  - '[[2026-06-10-graph-backend-P03-S26]]'
  - '[[2026-06-10-graph-backend-P03-S27]]'
  - '[[2026-06-10-graph-backend-P03-summary]]'
  - '[[2026-06-10-graph-backend-P04-S28]]'
  - '[[2026-06-10-graph-backend-P04-S29]]'
  - '[[2026-06-10-graph-backend-P04-S30]]'
  - '[[2026-06-10-graph-backend-P04-S31]]'
  - '[[2026-06-10-graph-backend-P04-S32]]'
  - '[[2026-06-10-graph-backend-P04-S33]]'
  - '[[2026-06-10-graph-backend-P04-summary]]'
  - '[[2026-06-10-graph-backend-adr]]'
  - '[[2026-06-10-graph-backend-plan]]'
  - '[[2026-06-10-graph-backend-research]]'
---

# `graph-backend` feature index

Auto-generated index of all documents tagged with `#graph-backend`.

## Documents

### adr

- `2026-06-10-graph-backend-adr` - `graph-backend` adr: `gui graph backend hardening` | (**status:** `accepted`)

### exec

- `2026-06-10-graph-backend-P01-S01` - pass an explicit edges keyword to the node-link serialisation call so the wire key is version-independent
- `2026-06-10-graph-backend-P01-S02` - raise the networkx dependency floor to 3.6
- `2026-06-10-graph-backend-P01-S03` - eliminate the duplicate metrics computation on the JSON export path
- `2026-06-10-graph-backend-P01-S04` - bump the graph envelope schema to vaultspec.vault.graph.v2
- `2026-06-10-graph-backend-P01-S05` - add a full-envelope v2 contract test asserting schema, status, every node field, every edge field, and metrics keys
- `2026-06-10-graph-backend-P01-S06` - add archive-resolution branch tests covering link resolution against the archive directory
- `2026-06-10-graph-backend-P01-S07` - add feature-scoped centrality assertions and replace the early-returning collision fan-out test with a guaranteed assertion
- `2026-06-10-graph-backend-P01-summary` - `graph-backend` `P01` summary
- `2026-06-10-graph-backend-P02-S08` - preserve wiki-link and related-link multiplicity by returning per-target counts from the extractors
- `2026-06-10-graph-backend-P02-S09` - audit and update every extractor call site for the counted return shape
- `2026-06-10-graph-backend-P02-S10` - attach kind, multiplicity, and normalised weight attributes to explicit edges during graph build
- `2026-06-10-graph-backend-P02-S11` - create the derived relatedness edge module computing reciprocity, shared-tag, jaccard, adamic-adar, and co-citation signals with documented composition coefficients
- `2026-06-10-graph-backend-P02-S12` - add pagerank and in-degree node-size hints as node attributes
- `2026-06-10-graph-backend-P02-S13` - add ego-graph local scoping by node and depth to the graph query surface
- `2026-06-10-graph-backend-P02-S14` - emit explicit edge attributes and the derived edge set in the v2 JSON payload
- `2026-06-10-graph-backend-P02-S15` - add node, depth, and derived-edge toggles to the vault graph verb
- `2026-06-10-graph-backend-P02-S16` - add exact-value tests for multiplicity, edge attributes, and normalised weights on the synthetic corpus
- `2026-06-10-graph-backend-P02-S17` - add exact-value tests for every derived signal and the composed weight
- `2026-06-10-graph-backend-P02-S18` - add CLI tests for ego scoping and derived-edge toggles
- `2026-06-10-graph-backend-P02-S19` - regenerate the bundled CLI reference and propagate provider sync
- `2026-06-10-graph-backend-P02-summary` - `graph-backend` `P02` summary
- `2026-06-10-graph-backend-P03-S20` - extract the related-frontmatter line surgery from the dangling fixer into a shared CRLF-preserving atomic helper
- `2026-06-10-graph-backend-P03-S21` - create the vault link command group with the list verb and versioned JSON envelopes
- `2026-06-10-graph-backend-P03-S22` - implement vault link add with target resolution, dangling refusal behind force, and dry-run preview
- `2026-06-10-graph-backend-P03-S23` - implement vault link remove reusing the shared related-entry surgery with dry-run preview
- `2026-06-10-graph-backend-P03-S24` - register the link group on the vault command app and wire the exit-code contract
- `2026-06-10-graph-backend-P03-S25` - add CRLF-preservation, atomic-write, and round-trip tests for the shared surgery helper
- `2026-06-10-graph-backend-P03-S26` - add CLI tests for link add, remove, and list covering dry-run, JSON envelopes, dangling refusal, and exit codes
- `2026-06-10-graph-backend-P03-S27` - regenerate the bundled CLI reference and propagate provider sync
- `2026-06-10-graph-backend-P03-summary` - `graph-backend` `P03` summary
- `2026-06-10-graph-backend-P04-S28` - create the fingerprint cache module with a size and mtime manifest and a serialised graph store
- `2026-06-10-graph-backend-P04-S29` - wire cache loading into graph construction with any fingerprint mismatch falling back to full rebuild
- `2026-06-10-graph-backend-P04-S30` - invalidate or refresh the graph cache from every mutating verb that touches vault documents
- `2026-06-10-graph-backend-P04-S31` - add cache correctness tests proving a stale cache is never trusted
- `2026-06-10-graph-backend-P04-S32` - add 500 and 5000 document scale benchmarks with generous thresholds
- `2026-06-10-graph-backend-P04-S33` - register the dedicated benchmark marker
- `2026-06-10-graph-backend-P04-summary` - `graph-backend` `P04` summary

### plan

- `2026-06-10-graph-backend-plan` - `graph-backend` plan

### research

- `2026-06-10-graph-backend-research` - `graph-backend` research: `hardened graph backend for gui visualisation`
