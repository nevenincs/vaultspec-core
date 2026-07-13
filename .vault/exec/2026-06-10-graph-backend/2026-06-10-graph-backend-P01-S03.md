---
tags:
  - '#exec'
  - '#graph-backend'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S03
related:
  - '[[2026-06-10-graph-backend-plan]]'
---

# eliminate the duplicate metrics computation on the JSON export path

## Scope

- `src/vaultspec_core/graph/api.py`

## Description

- Added a private `_g` keyword parameter to `VaultGraph.metrics()` in `src/vaultspec_core/graph/api.py`; when supplied, the internal `subgraph()` call is skipped.
- Updated `VaultGraph.to_dict()` to pass the already-computed subgraph as `_g=g` to `metrics()`, eliminating the second `subgraph()` traversal and the resulting duplicate `nx.betweenness_centrality` computation.
- Documented the `_g` parameter as intentionally private in the docstring.

## Outcome

`nx.betweenness_centrality` (O(V\*E)) runs at most once per `to_dict` call instead of twice. Output shape is unchanged. All 58 graph tests pass.

## Notes

No incidents. The `_g` underscore convention signals the private nature of the parameter without altering the public `metrics(feature=...)` call-site.
