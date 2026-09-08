---
tags:
  - '#exec'
  - '#test-provisioning-economics'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:1ea39a4fc6154799aafaa3a34e17122405392d15f95153e33a5e7df19bd59aaf'
related:
  - "[[2026-09-08-test-provisioning-economics-plan]]"
---

# `test-provisioning-economics` ledger

## Changes

- `S01` `M` `conftest.py`
- `S01` `verify:` `pytest src/vaultspec_core/tests/cli/test_cli_live.py` -> `pass`
- `S02` `A` `dev/guards/test_durability_boundary.py`
- `S02` `verify:` `pytest dev/guards/test_durability_boundary.py` -> `pass`
- `S03` `M` `conftest.py`
- `S03` `verify:` `pytest src/vaultspec_core/tests/cli/test_cli_live.py` -> `pass`

## Notes

- `S01` 236 passed in 197.93s; setup median fell from ~20s to ~2s
- `S02` guard found a pre-existing production violation in cli/\_target.py; filed as #515, allowlisted with a staleness check rather than silently exempted
- `S03` boundary measured: 236-test file 197.93s against a pre-change run still incomplete at 20min under equal load
