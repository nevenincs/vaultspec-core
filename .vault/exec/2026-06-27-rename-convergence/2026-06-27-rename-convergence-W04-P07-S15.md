---
tags:
  - '#exec'
  - '#rename-convergence'
date: '2026-06-27'
modified: '2026-06-27'
step_id: 'S15'
related:
  - "[[2026-06-27-rename-convergence-plan]]"
---

# Add the vault check feature-rename-integrity CLI command

## Scope

- `src/vaultspec_core/cli/vault_cmd.py`

## Description

- Add a `feature-rename-integrity` subcommand to the vault check command group, modeled exactly on the encoding check command, with `--verbose`, `--json`, and `--target` options and no `--feature` filter.
- Route the result through the shared render-and-exit helper with the command identifier `vault.check.feature-rename-integrity`.

## Outcome

- `vaultspec-core vault check feature-rename-integrity` runs standalone and emits a valid JSON envelope under schema `vaultspec.vault.check.feature-rename-integrity.v1`.

## Notes

- The command is vault-wide with no feature filter, consistent with the sibling encoding check.
