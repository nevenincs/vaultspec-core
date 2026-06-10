---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
step_id: S61
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# retier the wave-assuming verification hint at line 173 so it holds at every tier (D14)

## Scope

- `src/vaultspec_core/builtins/templates/plan.md`

## Description

- Reword the Verification hint's completion criterion from "every Step in every Wave
  is closed" to the tier-neutral "every Step in the plan is closed"
- Format the template with mdformat at wrap 88

## Outcome

The Verification hint no longer assumes Waves exist: Waves only appear at L3 and L4,
while the completion criterion applies at every tier. The L4-specific
Epic-completion sentence in the same hint is untouched because it is already
tier-qualified. Template annotation tests pass.

## Notes

None.
