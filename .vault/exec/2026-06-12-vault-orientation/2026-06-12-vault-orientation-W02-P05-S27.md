---
tags:
  - '#exec'
  - '#vault-orientation'
date: '2026-06-12'
modified: '2026-06-13'
step_id: S27
related:
  - '[[2026-06-12-vault-orientation-plan]]'
---

# add orientation core tests over a synthetic vault covering rollup, recency fallback, and unlinked-record reporting

## Scope

- `src/vaultspec_core/vaultcore/tests/test_orientation.py`

## Description

- Evaluate the synthetic-corpus generator and find it does not emit plan-step rows, exec `step_id` linkage, or the `modified` stamp this surface needs; build a small real vault in `tmp_path` by writing genuine vault documents instead.
- Add real-vault builders that render an L2 plan with explicit phase steps, execution records with and without `step_id`, and adr and research grounding documents with controllable `date` and `modified` values.
- Cover rollup active-feature ordering by modified recency, the date fallback when no stamp is present, and modified overriding an older date for ordering.
- Cover in-flight detection with open and closed step counts and completion percent, a fully closed plan dropping out, and most-recently-modified-first ordering.
- Cover the `limit` cap and the `since_days` day-window with a deterministic `today`, plus recent-document grouping by type.
- Cover step-to-record mapping including the no-record state for an open step and the unlinked bucket for a step-less exec record, tier-conditional display paths, and grounding grouped by type.
- Cover plan-path and feature-tag targets, a feature spanning two plans, and the unknown-target error with near-matches.

## Outcome

- 18 orientation tests pass; the full targeted suite reports 675 passed. Ruff format, ruff check, and ty check all clean. No mocks, patches, or skips; every assertion reads structures computed from real files.

## Notes

- The synthetic generator was assessed and rejected for this surface because it lacks plan hierarchy, step-id linkage, and the recency stamp; the hand-built real vault gives precise control over those exact dimensions the tests assert on.
