---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
step_id: S92
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# replace em dashes with spaced hyphens (D15)

## Scope

- `src/vaultspec_core/builtins/reference/cli.md`

## Description

- Replace the two remaining em dashes with spaced hyphens in the vault feature
  archive and vault feature unarchive section lead lines
- Format the reference with mdformat at wrap 88

## Outcome

The bundled CLI reference contains zero em dashes per decision D15; verification grep
for the em dash character across the file returns zero matches. Only two em dashes
remained after the P03 reference update; both were in section lead sentences that the
P03 Steps themselves introduced, and both now use the spaced-hyphen convention.

## Notes

None.
