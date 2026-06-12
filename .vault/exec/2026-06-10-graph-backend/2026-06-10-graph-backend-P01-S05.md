---
tags:
  - '#exec'
  - '#graph-backend'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S05
related:
  - '[[2026-06-10-graph-backend-plan]]'
---

# add a full-envelope v2 contract test asserting schema, status, every node field, every edge field, and metrics keys

## Scope

- `src/vaultspec_core/graph/tests/test_contract.py`

## Description

- Created `src/vaultspec_core/graph/tests/test_contract.py` with `TestGraphEnvelopeV2Contract` (11 tests).
- Defined `_EXPECTED_ENVELOPE_KEYS`, `_EXPECTED_DATA_KEYS`, `_EXPECTED_NODE_FIELDS`, `_EXPECTED_EDGE_FIELDS`, and `_EXPECTED_METRICS_KEYS` as frozen sets; any field change that does not update these constants causes a test failure.
- Added assertions for: schema string (`vaultspec.vault.graph.v2`), top-level envelope keys, status key, data payload keys, every node field, every edge field, every metrics key, JSON round-trip, `directed` flag, `max_in_degree`/`max_out_degree` shape, and feature-scoped envelope.
- Fixed `ty` type errors by using `dict[str, Any]` locals instead of direct subscript on `object`.

## Outcome

11 new contract tests pass. The test suite will reject any field addition, removal, or rename in the v2 payload that does not update the expected-field constants.

## Notes

No incidents. The `# type: ignore[index]` markers were replaced with typed local variables to satisfy `ty` without suppressions.
