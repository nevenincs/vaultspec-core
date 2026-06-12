---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S81
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# fix the continously typo and repair the garbled rolling-log-of-task-queue phrase (D15)

## Scope

- `src/vaultspec_core/builtins/skills/vaultspec-code-review/SKILL.md`

## Description

- Correct "continously" to "continuously" in the rolling-log bullet of the IMPORTANT
  section
- Repair the garbled phrase "appended to audit document as a rolling log of task
  queue" to "appended to the audit document as a rolling log of open tasks"
- Format the skill with mdformat at wrap 88

## Outcome

Both typo-inventory items the research charged to this file are resolved per decision
D15. Verification grep across the file for `continously` and `log of task queue`
returns zero matches; the repaired bullet now reads as a grammatical sentence.

## Notes

None.
