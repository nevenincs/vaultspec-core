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

Every node now carries deterministic node-size hints: a `pagerank` float and a
raw `in_degree` integer, both flowing through `node_link_data` serialisation.
At S12 commit time the only test coverage for the new field was the v2 contract
test asserting the `pagerank` and `in_degree` keys exist on every node; no
value-level behavioural test of the PageRank helper was committed. The helper's
mathematical behaviour (stochastic sums, symmetric-cycle uniformity, hub
ranking, dangling-mass conservation, determinism) was reasoned about but not
asserted by a committed test until the P02 review remediation (see Notes). All
graph tests passed at S12 commit; ruff, ruff-format, and ty were clean.

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

P02 review HIGH-1 remediation: the missing behavioural coverage was added in a
follow-up commit as `src/vaultspec_core/graph/tests/test_pagerank.py`, which
asserts the symmetric 3-cycle yields exactly `1/3` per node and a vector summing
to `1.0`, a star hub ranks strictly above its leaves, a dangling node still
yields a vector summing to `1.0`, the empty graph yields `{}`, and edges
inserted in different orders yield bit-identical scores. To make the
order-independence a genuine guarantee rather than a near-equality, the helper
was changed in the same remediation to iterate nodes in sorted key order (the
floating-point reduction order otherwise leaked insertion order into the last
ulp of every score); the earlier Description's "graph node order" phrasing is
superseded by sorted-key order. The helper also now logs a warning on
non-convergence before returning the last iterate (review LOW-1).
