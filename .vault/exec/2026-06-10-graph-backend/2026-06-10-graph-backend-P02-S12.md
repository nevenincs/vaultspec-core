---
tags:
  - '#exec'
  - '#graph-backend'
date: '2026-06-10'
step_id: S12
related:
  - '[[2026-06-10-graph-backend-plan]]'
---

# add pagerank and in-degree node-size hints as node attributes

## Scope

- `src/vaultspec_core/graph/api.py`

## Description

- Add a graph build pass 4 that attaches a `pagerank` float and a raw
  `in_degree` integer to every node so a GUI can size nodes without
  recomputing; both flow through `node_link_data` serialisation.
- Pin the PageRank damping factor as a module constant so node-size hints are
  reproducible and exactly testable.
- Implement a pure-Python deterministic power-iteration PageRank helper
  because networkx 3.6 routes its `pagerank` through a SciPy sparse solver and
  this project ships neither NumPy nor SciPy; the helper uses a uniform
  initial vector, graph node order, uniform dangling-mass redistribution, and
  edge-weight biasing, matching the networkx defaults.
- Update the v2 contract test's expected node field set to include `pagerank`
  and `in_degree`.

## Outcome

Every node now carries deterministic node-size hints. The PageRank helper sums
to exactly 1.0, returns uniform scores on a symmetric cycle, and ranks a star
hub below its leaves; repeated calls are bit-identical. All 81 graph tests
pass; ruff, ruff-format, and ty are clean.

## Notes

The mandate named `nx.pagerank`, but on this dependency set that call raises
`ModuleNotFoundError: No module named 'numpy'` because networkx 3.6 delegates
to a SciPy solver. Pulling in NumPy or SciPy would violate the ADR's
zero-new-dependency constraint, so the deterministic pure-Python power
iteration is the faithful substitute: same damping, same dangling and
teleport semantics, fully deterministic, and exactly testable without
floating-point tolerance on the convergence sums. The helper matches the
networkx node-count-scaled convergence test (`err < n * tol`, `tol=1e-6`) so
the real 658-node vault converges; on non-convergence it returns the last
mass-conserving iterate rather than raising, so a graph build can never crash
on node sizing. The contract node-field update is intentional evolution of the
still-unshipped v2 schema.
