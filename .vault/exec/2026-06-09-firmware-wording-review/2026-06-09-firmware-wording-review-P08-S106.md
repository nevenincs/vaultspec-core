---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
step_id: S106
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# convert the numbered procedural lists to bullets per the operations fragment mandate (D15)

## Scope

- `src/vaultspec_core/builtins/rules/vaultspec-dry-run-discipline.builtin.md`

## Description

- Verify the file for numbered procedural lists before editing
- Trace the resolution to the P02.S12 shortening, which rewrote the rule body with the
  five-step numbered procedure replaced by Good/Bad example bullets

## Outcome

Already resolved by P02.S12: the rule shortening replaced the original five-step
numbered procedure in the How section with bulleted Good/Bad worked examples. Grep
evidence: a search for the numbered-list pattern (a line starting with digits followed
by a dot or parenthesis) across every file in `src/vaultspec_core/builtins/rules/`
returns zero matches, so no edit is needed. The commit for this Step carries the record
and plan state only.

## Notes

No builtin file changed in this Step.
