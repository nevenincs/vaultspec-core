---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S108
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# remove the orphan end-conventions comment marker (D15)

## Scope

- `src/vaultspec_core/builtins/system/03-vaultspec.md`

## Description

- Remove the trailing orphan marker comment at the end of the file, which has no
  matching opening marker anywhere in the fragment
- Format the fragment with mdformat at wrap 88

## Outcome

The system fragment no longer ends with a dangling HTML comment marker whose opening
counterpart does not exist, per decision D15. Verification grep across the file returns
zero HTML comment markers of any kind, so the fragment now contains prose and tables
only.

## Notes

None.
