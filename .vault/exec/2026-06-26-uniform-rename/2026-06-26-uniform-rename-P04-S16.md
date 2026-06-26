---
tags:
  - '#exec'
  - '#uniform-rename'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S16'
related:
  - "[[2026-06-26-uniform-rename-plan]]"
---

# Test exec folder and exec record rename with preserved plan-date prefix

## Scope

- `src/vaultspec_core/vaultcore/tests/test_rename_feature.py`

## Description

- Added `TestExecRename` with an exec folder `{plan_date}-{old}/` containing a step record and a phase summary, where the plan date is deliberately distinct from the authored documents' date.
- Assert the folder and both records are renamed with the `{plan_date}` prefix preserved verbatim, the old record names do not survive, and the step record's feature tag is rewritten.

## Outcome

Two tests pass. The exec folder and records move under the new feature segment while the parent plan date stays fixed.

## Notes

Using a distinct plan date proves the prefix is preserved, not recomputed from the records' own frontmatter date.
