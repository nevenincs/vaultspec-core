---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S94
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# replace em dashes with spaced hyphens (D15)

## Scope

- `src/vaultspec_core/builtins/rules/vaultspec-codify.builtin.md`

## Description

- Replace the four em dashes with spaced hyphens: the durable-lesson appositive pair
  in the opening paragraph, the constraint's-origin dash in the Why bullet, and the
  most-produce-zero dash in the audit-driven codification bullet
- Format the rule with mdformat at wrap 88

## Outcome

The codify rule contains zero em dashes per decision D15; verification grep for the
em dash character across the file returns zero matches and the four replacement sites
read naturally with the spaced-hyphen convention. The arrow characters in the
pipeline phrase (research, decide, plan, execute, review, codify) are untouched, as
they are pipeline notation rather than punctuation dashes.

## Notes

None.
