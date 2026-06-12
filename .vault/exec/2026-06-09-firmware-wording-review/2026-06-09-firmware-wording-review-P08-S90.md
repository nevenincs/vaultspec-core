---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S90
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# replace the British spellings with American forms (D15)

## Scope

- `src/vaultspec_core/builtins/skills/vaultspec-codify/SKILL.md`

## Description

- Replace "changed at the centre" with "changed at the center" in the Supersede bullet
  of the Supersession discipline section
- Verify no other inventoried British spelling (serialiser, behaviour) remains in the
  file
- Format the skill with mdformat at wrap 88

## Outcome

The single British spelling in this skill is Americanized per decision D15.
Verification grep across the file for `serialiser`, `behaviour`, and `centre` returns
zero matches.

## Notes

None.
