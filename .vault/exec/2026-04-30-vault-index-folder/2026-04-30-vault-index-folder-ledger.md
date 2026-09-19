---
tags:
  - '#exec'
  - '#vault-index-folder'
date: '2026-04-30'
modified: '2026-09-19'
body_schema: 'body-v2'
body_hash: 'sha256:0f4a02b5e5cc767e249ac72fabd7d0a79240b5ed824e9fc1fe98f8d5a80c8127'
related:
  - "[[2026-09-19-vault-index-folder-plan]]"
---

# `vault-index-folder` ledger

## Changes

- `S01` `M` `src/vaultspec_core/core/enums.py`
- `S01` `M` `src/vaultspec_core/config/config.py`
- `S01` `M` `src/vaultspec_core/vaultcore/models.py`
- `S01` `M` `src/vaultspec_core/vaultcore/scanner.py`
- `S01` `M` `src/vaultspec_core/vaultcore/index.py`
- `S01` `M` `src/vaultspec_core/config/tests/test_config.py`
- `S01` `M` `src/vaultspec_core/vaultcore/tests/test_index.py`
- `S01` `M` `src/vaultspec_core/vaultcore/tests/test_scanner.py`
- `S02` `M` `src/vaultspec_core/vaultcore/checks/structure.py`
- `S02` `M` `src/vaultspec_core/vaultcore/checks/features.py`
- `S02` `M` `src/vaultspec_core/vaultcore/checks/tests/test_index_safety.py`
- `S02` `A` `src/vaultspec_core/vaultcore/checks/tests/test_index_migration.py`
- `S02` `M` `src/vaultspec_core/cli/vault_cmd.py`
- `S02` `M` `src/vaultspec_core/testing/synthetic.py`
- `S02` `M` `.vaultspec/rules/templates/index.md`
- `S03` `M` `README.md`
- `S03` `M` `.vaultspec/CLI.md`
- `S03` `M` `.vaultspec/rules/rules/vaultspec.builtin.md`
- `S03` `A` `.vault/index/vault-index-folder.index.md`

## Notes

- `S01` Rows backfilled from the feature's historical execution records; this plan and ledger were reconstructed after execution, not logged contemporaneously.
