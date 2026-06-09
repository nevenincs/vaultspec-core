---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-09'
step_id: S03
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# replace the phantom vaultspec-write-plan skill name with vaultspec-write in the pipeline cross-reference at line 24 (D1)

## Scope

- `src/vaultspec_core/builtins/skills/vaultspec-code-research/SKILL.md`

## Description

- Replace `vaultspec-write-plan` with `vaultspec-write` in the pipeline cross-reference sentence of `src/vaultspec_core/builtins/skills/vaultspec-code-research/SKILL.md`
- Run mdformat on the edited file

## Outcome

The research-to-plan pipeline cross-reference now names the shipped `vaultspec-write` skill directory, implementing ADR decision D1. Verified by grep: zero `vaultspec-write-plan` matches remain anywhere under `src/vaultspec_core/builtins/`.

## Notes

None.
