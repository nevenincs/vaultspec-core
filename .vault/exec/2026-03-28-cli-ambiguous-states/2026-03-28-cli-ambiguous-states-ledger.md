---
tags:
  - '#exec'
  - '#cli-ambiguous-states'
date: '2026-03-28'
modified: '2026-09-19'
body_schema: 'body-v2'
body_hash: 'sha256:72b683604c1534f1928fbf0c284ecb4fdce0496496d4bd0e9769da579d6e8597'
related:
  - "[[2026-03-28-cli-ambiguous-states-audit-fixes-plan]]"
---

# `cli-ambiguous-states` ledger

## Changes

- `S01` `A` `src/vaultspec_core/core/helpers.py`
- `S02` `M` `src/vaultspec_core/core/mcps_native.py`
- `S03` `M` `src/vaultspec_core/core/provision.py`
- `S04` `M` `src/vaultspec_core/core/uninstall.py`
- `S05` `M` `src/vaultspec_core/cli/rendering_outcomes.py`
- `S06` `M` `src/vaultspec_core/core/agents.py`
- `S07` `M` `src/vaultspec_core/cli/_errors.py`
- `S08` `M` `src/vaultspec_core/cli/root_preflight.py`
- `S09` `A` `src/vaultspec_core/core/config_gen.py`
- `S10` `M` `src/vaultspec_core/core/provision.py`
- `S11` `M` `src/vaultspec_core/core/provision.py`
- `S12` `M` `src/vaultspec_core/core/sync.py`

## Notes

- `S01` Rows backfilled from the plan's declared Step targets; this ledger was reconstructed after execution, not logged contemporaneously.
