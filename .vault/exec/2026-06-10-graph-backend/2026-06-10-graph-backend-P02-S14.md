---
tags:
  - '#exec'
  - '#graph-backend'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S14
related:
  - '[[2026-06-10-graph-backend-plan]]'
---

# emit explicit edge attributes and the derived edge set in the v2 JSON payload

## Scope

- `src/vaultspec_core/graph/api.py`

## Description

- Extend `to_dict` to add a separate `derived_edges` array carrying the
  implicit relatedness edges, computed on demand and never mixed into the
  canonical `edges` array, so checker semantics over the canonical graph stay
  intact.
- Add `node`/`depth` ego scoping and an `include_derived` toggle to `to_dict`;
  scoping precedence is node ego, then feature, then full graph.
- Scope the emitted derived edges to the exported node set so a feature- or
  ego-scoped payload only carries derived edges with both endpoints present.
- Confirm the explicit-edge attributes (`kind`, `multiplicity`, `weight`) and
  node-size hints (`pagerank`, `in_degree`) already flow through
  `node_link_data` onto edges and nodes.
- Add `derived_edges` to the v2 contract test's expected data-key set,
  completing the schema evolution begun by the edge-field and node-field
  updates in the prior graph-build steps.

## Outcome

The v2 payload now carries typed weighted explicit edges, node-size hints, and
a separate derived relatedness array, with optional ego and feature scoping
and a derived-edge toggle. A probe confirmed the full payload exposes nine data
keys including `derived_edges`, every node carries `pagerank` and `in_degree`,
every canonical edge carries `kind`/`multiplicity`/`weight`, `include_derived`
False empties the derived array, and ego scoping filters derived edges to the
scoped node set. All 81 graph tests pass; ruff, ruff-format, and ty are clean.

## Notes

The canonical `edges` array and the `derived_edges` array are strictly
disjoint: the derived set is computed by the separate derived module and never
inserted into the DiGraph, honouring the architectural constraint that
checker-facing edges mean real authored references. The contract test
data-key, edge-field, and node-field updates across the graph-build steps are
deliberate, test-visible evolution of the still-unshipped v2 schema, not a
freeze-test bypass.
