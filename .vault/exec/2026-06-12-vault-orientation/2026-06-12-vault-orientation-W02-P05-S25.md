---
tags:
  - '#exec'
  - '#vault-orientation'
date: '2026-06-12'
modified: '2026-06-13'
step_id: S25
related:
  - '[[2026-06-12-vault-orientation-plan]]'
---

# extend plan status with a batched all-plans collector sharing one exec-record step-id index

## Scope

- `src/vaultspec_core/plan/status.py`

## Description

- Add `ExecRecordIndex`, a dataclass that scans every execution record once via a single `list_documents(doc_type="exec")` pass and maps `(feature, step_id)` to the record stem, with a parallel unlinked-by-feature bucket for records that carry no resolvable `step_id` frontmatter.
- Add the `_plan_feature` helper that extracts a plan's single feature tag, shared by both status paths.
- Refactor `collect_status` to accept an optional pre-built `exec_index`; when supplied the per-call exec rescan is skipped and the shared index is reused, when omitted but a root is given a single-plan index is built, preserving the existing single-plan signature.
- Add `PlanStatusEntry` and `collect_all_statuses`, which builds the shared index once, parses every plan once, and computes each plan's status against the shared index. An unparseable plan is collected with an `error` note instead of aborting the batch.
- Keep `status_to_json_dict` and the `PlanStatus` schema byte-stable.

## Outcome

- The batched core (decision D6) is in place: one exec scan and one parse per plan, shared by the single-plan and all-plans surfaces.
- Targeted tests pass: `uv run --no-sync pytest src/vaultspec_core/tests/plan/test_status.py -q -p no:randomly` reports 12 passed. Ruff format, ruff check, and ty check all clean.

## Notes

- The unlinked bucket is computed here so the orientation trace in the next step can surface hand-written records that reference a plan without a resolvable step id, rather than dropping them.
