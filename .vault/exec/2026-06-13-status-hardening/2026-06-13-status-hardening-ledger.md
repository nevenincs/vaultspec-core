---
tags:
  - '#exec'
  - '#status-hardening'
date: '2026-06-13'
modified: '2026-09-19'
body_schema: 'body-v2'
body_hash: 'sha256:89114bc501ad471ef98cc140b532b25d14d7158d3bb123995cf31c04a5c8e6d6'
related:
  - "[[2026-06-13-status-hardening-plan]]"
---

# `status-hardening` ledger

## Changes

- `S01` `M` `src/vaultspec_core/plan/parser.py`
- `S02` `A` `src/vaultspec_core/plan/status.py`
- `S03` `A` `src/vaultspec_core/plan/status.py`
- `S04` `M` `src/vaultspec_core/vaultcore/orientation.py`
- `S05` `A` `src/vaultspec_core/tests/plan/test_status.py`
- `S06` `M` `src/vaultspec_core/cli/root.py`
- `S07` `M` `src/vaultspec_core/cli/vault_cmd.py`
- `S08` `A` `src/vaultspec_core/cli/rendering.py`
- `S09` `M` `src/vaultspec_core/cli/vault_cmd.py`
- `S10` `A` `src/vaultspec_core/vaultcore/orientation.py`
- `S11` `A` `src/vaultspec_core/tests/cli/test_vault_status.py`
- `S12` `M` `src/vaultspec_core/cli/vault_cmd.py`
- `S13` `A` `src/vaultspec_core/vaultcore/orientation.py`
- `S14` `M` `src/vaultspec_core/vaultcore/orientation.py`
- `S15` `A` `src/vaultspec_core/tests/cli/test_vault_status.py`
- `S16` `A` `src/vaultspec_core/cli/_target.py`
- `S17` `A` `src/vaultspec_core/tests/cli/test_plan_target.py`
- `S18` `M` `src/vaultspec_core/cli/plan_cmd.py`
- `S19` `M` `src/vaultspec_core/cli/plan_cmd.py`
- `S20` `M` `src/vaultspec_core/cli/plan_cmd.py`
- `S21` `A` `src/vaultspec_core/tests/cli/test_plan_target.py`
- `S22` `M` `src/vaultspec_core/vaultcore/orientation.py`
- `S23` `A` `src/vaultspec_core/tests/cli/test_vault_status.py`
- `S24` `M` `src/vaultspec_core/builtins/system/03-vaultspec.md`
- `S25` `M` `src/vaultspec_core/builtins/rules/vaultspec-cli.builtin.md`
- `S26` `M` `src/vaultspec_core/builtins/reference/cli.md`
- `S27` `M` `src/vaultspec_core/cli/_target.py`
- `S28` `A` `src/vaultspec_core/cli/vault_cmd.py`
- `S29` `M` `src/vaultspec_core/cli/rendering.py`
- `S30` `M` `src/vaultspec_core/tests`
- `S31` `M` `repository root`

## Notes

- `S01` Rows backfilled from the plan's declared Step targets; this ledger was reconstructed after execution, not logged contemporaneously.
