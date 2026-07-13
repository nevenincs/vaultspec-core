---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S60
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# update the plan heading example to the phase-less H1 form (D14)

## Scope

- `src/vaultspec_core/builtins/rules/vaultspec.builtin.md`

## Description

- Replace the General Rules heading example that canonized the phase-bearing plan H1
  with the phase-less form matching the S59 template change
- Format with mdformat at wrap 88

## Outcome

The Placeholder Naming Conventions' General Rules bullet now teaches the plan H1 as
the phase-less form, matching the template after S59. The research example in the
same sentence is untouched, and the trailing sentence keeps `{phase}` among the
canonical uppercase identifier segments because Phase headings and exec-summary
H1s still carry it. Template annotation tests pass.

## Notes

None.
