---
tags:
  - '#exec'
  - '#graph-backend'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S10
related:
  - '[[2026-06-10-graph-backend-plan]]'
---

# attach kind, multiplicity, and normalised weight attributes to explicit edges during graph build

## Scope

- `src/vaultspec_core/graph/api.py`

## Description

- Add a `_edge_kind` helper that maps the per-edge provenance set to a single
  `kind` value: `both` when reached by a body wiki-link and a `related` entry,
  otherwise the single source token (`body` or `related`).
- Attach `kind` and `multiplicity` to both `add_edge` call sites (real-target
  and phantom-target) during graph build pass 2, reading the combined count
  and unioned provenance threaded through in the prior step.
- Add a pass 2b that normalises `weight` against the maximum edge
  multiplicity in the graph: `weight = multiplicity / max_multiplicity`, so
  the strongest edge is exactly `1.0` and an empty graph normalises to `0.0`.
- Document the three edge attributes and the normalisation scheme on the
  `VaultGraph` class docstring, cross-referencing the derived-edge module.
- Update the v2 contract test's expected edge field set to include `kind`,
  `multiplicity`, and `weight`, since `node_link_data` serialises edge
  attributes immediately and the schema is still the unshipped v2.

## Outcome

Every explicit canonical-graph edge now carries a provenance `kind`, an
integer `multiplicity`, and a deterministic normalised `weight` that flow
through `node_link_data` serialisation without extra wiring. The strongest
edge weights to exactly 1.0; weights are exact rationals testable without
tolerance. All 81 graph tests pass, ruff and ty are clean.

## Notes

The `kind` enum is `body` / `related` / `both`. The weight normalisation is a
single linear division by the graph-wide maximum multiplicity, chosen because
it is deterministic and yields exact rationals on the synthetic corpus, where
most edges have multiplicity 1 and therefore weight 1.0. The contract test
edge-field update is intentional schema evolution within the still-unshipped
v2 envelope, not a freeze-test bypass; the same file gains the
`derived_edges` payload key and node-size node fields in the payload-emission
step.
