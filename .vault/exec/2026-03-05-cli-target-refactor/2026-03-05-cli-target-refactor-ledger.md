---
tags:
  - '#exec'
  - '#cli-target-refactor'
date: '2026-03-05'
modified: '2026-09-19'
body_schema: 'body-v2'
body_hash: 'sha256:b96c13ccebf905194ee7ce384d9656273ff2d7884603ae4f7a5d49b39b30648b'
related:
  - "[[2026-03-05-cli-target-refactor-plan]]"
---

# `cli-target-refactor` ledger

## Changes

- `S01` `M` `src/vaultspec_core/core/__init__.py`
- `S02` `M` `src/vaultspec_core/config/workspace.py`
- `S03` `M` `src/vaultspec_core/config/config.py`
- `S04` `A` `src/vaultspec_core/cli/_app.py`
- `S05` `M` `src/vaultspec_core/logging_config.py`
- `S06` `M` `src/vaultspec_core/core/`
- `S07` `M` `src/vaultspec_core/core/`
- `S08` `A` `src/vaultspec_core/cli/`
- `S09` `M` `src/vaultspec_core/cli/root_install.py`
- `S10` `M` `src/vaultspec_core/hooks/engine.py`
- `S12` `D` `src/vaultspec/vault_cli.py`
- `S11` `A` `src/vaultspec_core/tests/cli/`

## Notes

- `S01` Rows backfilled from the plan's declared Step targets and the feature's historical execution records; this ledger was reconstructed after execution, not logged contemporaneously.
