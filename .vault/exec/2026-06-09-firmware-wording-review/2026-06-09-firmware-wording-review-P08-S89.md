---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
body_hash: 'sha256:c62a2020116a0501576a6451571f40a9086d3186e567288b8f4e8a79735a1b49'
step_id: S89
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# replace the British spellings with American forms (D15)

## Scope

- `src/vaultspec_core/builtins/rules/vaultspec-codify.builtin.md`

## Description

- Replace "changed at the centre" with "changed at the center" in the Supersede bullet
  of the when-a-rule-becomes-wrong section
- Verify no other inventoried British spelling (serialiser, behaviour) remains in the
  file
- Format the rule with mdformat at wrap 88

## Outcome

The single British spelling in this rule is Americanized per decision D15.
Verification grep across the file for `serialiser`, `behaviour`, and `centre` returns
zero matches. The em dashes still present in the file are deliberately untouched
here; the plan assigns them to the dedicated dash sweep Step S94 on this same file.

## Notes

None.
