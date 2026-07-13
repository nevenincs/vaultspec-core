---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S91
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# replace the British spellings with American forms (D15)

## Scope

- `src/vaultspec_core/builtins/agents/vaultspec-codifier.md`

## Description

- Replace "changed at the centre" with "changed at the center" in the Supersede bullet
  of the Supersession discipline section
- Verify no other inventoried British spelling (serialiser, behaviour) remains in the
  file
- Format the persona with mdformat at wrap 88

## Outcome

The single British spelling left in the codifier persona after the S87 wording repair
is Americanized per decision D15. Verification grep across the file for `serialiser`,
`behaviour`, and `centre` returns zero matches; the codify trio (rule, skill,
persona) now reads in one spelling locale.

## Notes

None.
