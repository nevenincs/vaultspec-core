---
tags:
  - '#exec'
  - '#vault-scale-performance'
date: '2026-07-27'
modified: '2026-07-27'
body_schema: 'body-v1'
body_hash: 'sha256:d111a5a69cf65351f4842757e8979080aa73c75a11bbfb6e7d2bf3fa225bf4f0'
step_id: 'S21'
related:
  - "[[2026-07-27-vault-scale-performance-plan]]"
---

# route the opt-in betweenness analysis through rustworkx with a networkx fallback and add the dependency

## Scope

- `src/vaultspec_core/graph/api.py`

## Description

- Add the analysis-engine seam routing betweenness centrality
  through rustworkx (converted graph, identical normalisation and
  endpoint semantics) with pure networkx as the automatic fallback
  when the wheel is unavailable.
- Declare the dependency with a version floor and update the
  metrics docstring to name the seam.

## Outcome

Measured on the real 1,181-node graph: 13.2x faster than networkx
(0.013s vs 0.168s) with a maximum score delta of 1.6e-19 - float
epsilon, not semantic divergence. The advantage grows with corpus
size since the algorithm is O(V\*E) and the engine parallelises
above a node threshold.

## Notes

Only the expensive opt-in algorithm is routed; the canonical graph
structure, cheap counts, pagerank, and every serialization stay on
networkx, keeping the wire contract and cache payload untouched.
