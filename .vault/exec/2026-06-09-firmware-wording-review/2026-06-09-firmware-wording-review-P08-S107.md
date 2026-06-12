---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S107
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# convert the numbered procedural lists to bullets per the operations fragment mandate (D15)

## Scope

- `src/vaultspec_core/builtins/rules/vaultspec-plan-editing-discipline.builtin.md`

## Description

- Verify the file for numbered procedural lists before editing
- Trace the resolution to the P02.S14 shortening, which replaced the two numbered
  canonical-ordering procedures with a bulleted How section

## Outcome

Already resolved by P02.S14: the rule shortening retired the ordering constraint the
two numbered procedures encoded (the six-step new-plan ordering and the three-step
revision ordering) and replaced the How section with bullets describing the
preserved-prose behavior. Grep evidence: a search for the numbered-list pattern (a line
starting with digits followed by a dot or parenthesis) across every file in
`src/vaultspec_core/builtins/rules/` returns zero matches, so no edit is needed. The
commit for this Step carries the record and plan state only.

## Notes

No builtin file changed in this Step.
