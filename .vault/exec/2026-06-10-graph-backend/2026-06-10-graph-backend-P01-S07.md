---
tags:
  - '#exec'
  - '#graph-backend'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S07
related:
  - '[[2026-06-10-graph-backend-plan]]'
---

# add feature-scoped centrality assertions and replace the early-returning collision fan-out test with a guaranteed assertion

## Scope

- `src/vaultspec_core/graph/tests/test_graph.py`

## Description

- Added `test_feature_scoped_centrality_populated` in `TestVaultGraphMetrics` asserting that `metrics(feature="editor-demo")` produces non-empty `in_degree_centrality` and `betweenness_centrality` dicts with normalised float values.
- Added `test_feature_scoped_centrality_keys_are_node_names` asserting that every centrality key belongs to the feature subgraph's node set.
- Replaced the body of `test_wiki_links_to_colliding_stems_fan_out` with unconditional assertions (collisions exist and each has 2+ qualified keys) - the prior implementation returned early without asserting anything when no linked collisions existed.
- Added `test_wiki_links_to_colliding_stems_fan_out_guaranteed` constructing a minimal vault (3 docs, 2 sharing a stem) on `tmp_path` and asserting unconditionally that the linker has edges to both collision variants.

## Outcome

4 new assertions added; the early-returning collision test now asserts unconditionally. Total graph test count: 81. All pass.

## Notes

No incidents. The guaranteed fan-out test uses `tmp_path` for isolation; it does not depend on the session-scoped synthetic corpus fixture.
