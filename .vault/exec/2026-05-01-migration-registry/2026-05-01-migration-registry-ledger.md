---
tags:
  - '#exec'
  - '#migration-registry'
date: '2026-05-01'
modified: '2026-09-19'
body_schema: 'body-v2'
body_hash: 'sha256:5b0d6eb5007ccfb56c4249409ebfe034a7036be73939252aed5191fcd2d09390'
related:
  - "[[2026-09-19-migration-registry-plan]]"
---

# `migration-registry` ledger

## Changes

- `S01` `M` `src/vaultspec_core/core/helpers.py`
- `S01` `M` `src/vaultspec_core/core/resolver.py`
- `S02` `A` `src/vaultspec_core/migrations/__init__.py`
- `S03` `A` `src/vaultspec_core/migrations/m_0_1_17_index_subfolder.py`
- `S04` `M` `src/vaultspec_core/core/provision.py`
- `S04` `M` `src/vaultspec_core/vaultcore/scanner.py`
- `S04` `M` `src/vaultspec_core/core/diagnosis/diagnosis.py`
- `S04` `M` `src/vaultspec_core/cli/spec_cmd_doctor.py`
- `S05` `A` `src/vaultspec_core/cli/migrations_cmd.py`
- `S06` `M` `src/vaultspec_core/vaultcore/checks/structure.py`
- `S07` `M` `.pre-commit-hooks.yaml`
- `S07` `M` `README.md`
- `S07` `M` `.vaultspec/CLI.md`
- `S07` `M` `.vaultspec/rules/rules/vaultspec-cli.builtin.md`

## Notes

- `S01` Rows backfilled from the feature's historical execution records; this plan and ledger were reconstructed after execution, not logged contemporaneously.
