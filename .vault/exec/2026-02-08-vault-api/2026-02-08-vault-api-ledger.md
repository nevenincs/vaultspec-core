---
tags:
  - '#exec'
  - '#vault-api'
date: '2026-02-08'
modified: '2026-09-19'
body_schema: 'body-v2'
body_hash: 'sha256:8851e731cf4c70d4e9c8bc37de6b90e84b20065b8ac658064921ddcfbbd66717'
related:
  - "[[2026-02-08-vault-api-plan]]"
---

# `vault-api` ledger

## Changes

- `S01` `A` `src/vaultspec_core/vaultcore`
- `S02` `A` `src/vaultspec_core/vaultcore/parser.py`
- `S03` `M` `src/vaultspec_core/graph/api.py`
- `S04` `A` `src/vaultspec_core/cli`
- `S05` `A` `src/vaultspec_core/cli`
- `S06` `A` `src/vaultspec_core/vaultcore/hydration.py`
- `S07` `A` `src/vaultspec_core/vaultcore/index.py`
- `S08` `M` `src/vaultspec_core/vaultcore/checks/features.py`
- `S09` `M` `src/vaultspec_core/vaultcore/checks/body_sections.py`
- `S13` `M` `src/vaultspec_core/vaultcore/checks/exec_mapping.py`
- `S10` `M` `src/vaultspec_core/mcp_server`
- `S11` `A` `src/vaultspec_core/vaultcore/checks/dangling.py`
- `S12` `M` `src/vaultspec_core/core/workspace_mode.py`

## Notes

- `S01` Rows backfilled from the plan's declared Step targets; this ledger was reconstructed after execution, not logged contemporaneously.
