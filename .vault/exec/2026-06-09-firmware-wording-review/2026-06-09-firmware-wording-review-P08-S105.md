---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
step_id: S105
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# drop the fragile third-worked-example ordinal (D15)

## Scope

- `src/vaultspec_core/builtins/rules/vaultspec-dry-run-discipline.builtin.md`

## Description

- Replace the opening "Third worked example of codification." with the ordinal-free "A
  worked example of codification."
- Format the rule with mdformat at wrap 88

## Outcome

The dry-run discipline rule no longer carries an ordinal that breaks whenever a sibling
discipline rule is added, removed, or reordered, per decision D15. The P02.S12
shortening had rewritten the rule's Why, How, and Status sections but left the opening
ordinal intact, so this was a real edit, not a no-op. The opening now parallels the
ordinal-free openers of the archive-discipline and plan-editing-discipline rules.

## Notes

None.
