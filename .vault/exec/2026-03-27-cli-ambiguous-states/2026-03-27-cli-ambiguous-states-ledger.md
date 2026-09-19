---
tags:
  - '#exec'
  - '#cli-ambiguous-states'
date: '2026-03-27'
modified: '2026-09-19'
body_schema: 'body-v2'
body_hash: 'sha256:87f42cf4c4d6c433e4ae5948253409dc99d511ac542646c4543b1139351d169a'
related:
  - "[[2026-03-27-cli-ambiguous-states-plan]]"
---

# `cli-ambiguous-states` ledger

## Changes

- `S01` `A` `src/vaultspec_core/core/diagnosis/signals.py`
- `S02` `M` `src/vaultspec_core/core/manifest.py`
- `S03` `A` `src/vaultspec_core/core/gitignore.py`
- `S04` `M` `src/vaultspec_core/tests/cli/test_signals.py`
- `S05` `A` `src/vaultspec_core/core/diagnosis/collectors.py`
- `S06` `A` `src/vaultspec_core/core/diagnosis/diagnosis.py`
- `S07` `M` `src/vaultspec_core/tests/cli/test_collectors.py`
- `S08` `A` `src/vaultspec_core/core/resolver.py`
- `S09` `A` `src/vaultspec_core/cli/root_doctor.py`
- `S10` `M` `src/vaultspec_core/tests/cli/test_resolver.py`
- `S11` `M` `src/vaultspec_core/cli/root_install.py`
- `S12` `M` `src/vaultspec_core/cli/root_install.py`
- `S13` `M` `src/vaultspec_core/cli/root_preflight.py`
- `S14` `M` `src/vaultspec_core/tests/cli/test_ambiguous_states.py`

## Notes

- `S01` Rows backfilled from the plan's declared Step targets; this ledger was reconstructed after execution, not logged contemporaneously.
