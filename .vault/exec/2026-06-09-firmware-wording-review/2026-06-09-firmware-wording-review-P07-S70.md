---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S70
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# align the documented date-quoting example with the quoted form the templates use (D14)

## Scope

- `src/vaultspec_core/builtins/rules/vaultspec.builtin.md`

## Description

- Quote the date value in the Tag Format YAML example so the rules show the same
  single-quoted form every shipped template scaffolds
- Format with mdformat at wrap 88

## Outcome

The Tag Format example now reads `date: '2026-02-06'`, matching the
`date: '{yyyy-mm-dd}'` form all nine templates carry and the quoted dates the
scaffolder writes into real vault documents. The rules' example was the only
unquoted-date occurrence in the conventions. Template annotation and rule contract
tests pass (10 passed).

## Notes

None.
