---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-09'
step_id: S01
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# replace the phantom vaultspec-write-plan skill name with vaultspec-write in the pipeline table at line 25 and the intent table at line 68 (D1)

## Scope

- `src/vaultspec_core/builtins/system/03-vaultspec.md`

## Description

- Replace `vaultspec-write-plan` with `vaultspec-write` in the pipeline table Plan row of `src/vaultspec_core/builtins/system/03-vaultspec.md`
- Replace `vaultspec-write-plan` with `vaultspec-write` in the intent table row "Plan the implementation"
- Run mdformat on the edited file

## Outcome

Both occurrences of the phantom skill name in `src/vaultspec_core/builtins/system/03-vaultspec.md` now name the shipped `vaultspec-write` skill directory, implementing ADR decision D1. Verified by grep: zero `vaultspec-write-plan` matches remain in the file; table layout intact after mdformat.

## Notes

None.
