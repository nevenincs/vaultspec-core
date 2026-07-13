---
tags:
  - '#exec'
  - '#graph-backend'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S13
related:
  - '[[2026-06-10-graph-backend-plan]]'
---

# add ego-graph local scoping by node and depth to the graph query surface

## Scope

- `src/vaultspec_core/graph/api.py`

## Description

- Add an `ego_subgraph(node, depth)` method to the graph query surface that
  returns the local neighbourhood around a centre node up to a hop radius,
  for Obsidian local-graph parity.
- Use `nx.ego_graph` with `undirected=True` so a backlink counts as local
  context, then induce the directed subgraph on the resulting node set so
  edge direction and the explicit-edge attributes survive.
- Validate inputs: raise `KeyError` for a missing centre node and `ValueError`
  for a negative depth; `depth=0` returns just the centre node.

## Outcome

The graph now answers local-graph queries by node and radius. A probe showed
`depth=0` yields the centre alone, the neighbourhood grows monotonically with
depth, edge `kind`/`weight` attributes are preserved on the induced subgraph,
and the input guards raise as specified. All 81 graph tests pass; ruff,
ruff-format, and ty are clean.

## Notes

Ego traversal is undirected because local-graph context is symmetric: a
document that links to the centre is as relevant to the local view as one the
centre links to. The returned graph is nonetheless the directed induced
subgraph, so direction and weighting are not lost; only the reachability
traversal ignores direction.
