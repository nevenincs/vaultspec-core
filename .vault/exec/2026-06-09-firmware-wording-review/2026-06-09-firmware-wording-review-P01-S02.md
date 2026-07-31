---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-09'
modified: '2026-06-13'
body_hash: 'sha256:f37ef43d5086f756e58350ea8408f348c5b68dbd6805795b9e3f0609bf40cf0c'
step_id: S02
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# replace the phantom vaultspec-write-plan skill name with vaultspec-write in the skill catalog at line 35 (D1)

## Scope

- `src/vaultspec_core/builtins/rules/vaultspec.builtin.md`

## Description

- Replace the `vaultspec-write-plan` catalog entry with `vaultspec-write` in the skill list of `src/vaultspec_core/builtins/rules/vaultspec.builtin.md`
- Run mdformat on the edited file

## Outcome

The skill catalog now names the shipped `vaultspec-write` skill directory, implementing ADR decision D1. Verified by grep: zero `vaultspec-write-plan` matches remain in the file.

## Notes

None.
