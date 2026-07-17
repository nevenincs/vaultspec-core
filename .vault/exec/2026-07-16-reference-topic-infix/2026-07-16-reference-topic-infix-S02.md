---
tags:
  - '#exec'
  - '#reference-topic-infix'
date: '2026-07-16'
modified: '2026-07-16'
step_id: 'S02'
related:
  - "[[2026-07-16-reference-topic-infix-plan]]"
---

# Add the --topic flag with shared-normalizer validation and non-admitting-type error to vault add

## Scope

- `src/vaultspec_core/cli/vault_cmd.py`

## Description

- Add the `--topic` flag to `vault add` with shared-normalizer kebab-case
  validation and a hard error for non-admitting types, passing the normalized
  value to the scaffolder.

## Outcome

CLI transport converges on the same builder; error wording mirrors the existing
step-flag validations. Modified: `src/vaultspec_core/cli/vault_cmd.py`.

## Notes

None.
