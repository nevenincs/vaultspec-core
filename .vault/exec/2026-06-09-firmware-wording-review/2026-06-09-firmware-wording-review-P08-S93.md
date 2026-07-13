---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S93
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# replace em dashes with spaced hyphens (D15)

## Scope

- `src/vaultspec_core/builtins/rules/vaultspec-archive-discipline.builtin.md`

## Description

- Verify the file for em dashes before editing
- Trace the resolution to the P02.S11 shortening, which rewrote the rule body without
  em dashes

## Outcome

Already resolved by P02.S11 (commit a3f002a): the rule shortening rewrote the body
and the em dashes the research inventoried went with the removed prose. Grep
evidence: a search for the em dash character across the file returns zero matches, so
no edit is needed. The commit for this Step carries the record and plan state only.

## Notes

No builtin file changed in this Step.
