---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
step_id: S104
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# drop the fragile second-worked-example ordinal (D15)

## Scope

- `src/vaultspec_core/builtins/rules/vaultspec-plan-editing-discipline.builtin.md`

## Description

- Replace the opening "Second worked example of codification applied to an audit
  finding." with the ordinal-free "A worked example of codification applied to an audit
  finding."
- Format the rule with mdformat at wrap 88

## Outcome

The plan-editing discipline rule no longer carries an ordinal that breaks whenever a
sibling discipline rule is added, removed, or reordered, per decision D15. The P02.S14
shortening had rewritten the rule's Why, How, and Status sections but left the opening
ordinal intact, so this was a real edit, not a no-op. The opening now parallels the
archive-discipline rule's ordinal-free "A working example" form.

## Notes

None.
