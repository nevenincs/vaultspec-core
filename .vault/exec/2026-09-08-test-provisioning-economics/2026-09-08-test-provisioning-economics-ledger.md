---
tags:
  - '#exec'
  - '#test-provisioning-economics'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:cb7247820490485c96f58b569bea7966dd15662ad65536cb60a6140ad9519e2b'
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
- `S04` `M` `src/vaultspec_core/tests/cli/conftest.py`
- `S04` `verify:` `pytest src/vaultspec_core -n 12` -> `pass`
- `S05` `M` `src/vaultspec_core/mcp_server/tests/conftest.py`
- `S05` `verify:` `pytest src/vaultspec_core -n 12` -> `pass`
- `S06` `M` `src/vaultspec_core/tests/cli/workspace_factory.py`
- `S06` `A` `src/vaultspec_core/tests/cli/test_workspace_template_reuse.py`
- `S06` `verify:` `pytest src/vaultspec_core/tests/cli/test_workspace_template_reuse.py` -> `pass`
- `S08` `M` `dev/toolchain.py`
- `S08` `verify:` `pytest src/vaultspec_core -n 12` -> `pass`

## Notes

- `S01` 236 passed in 197.93s; setup median fell from ~20s to ~2s
- `S02` guard found a pre-existing production violation in cli/\_target.py; filed as #515, allowlisted with a staleness check rather than silently exempted
- `S03` boundary measured: 236-test file 197.93s against a pre-change run still incomplete at 20min under equal load
- `S04` session template plus per-test clone
- `S05` session template plus per-test clone
- `S06` install() itself serves the default shape from a per-process template, covering all ~300 call sites; mcp-ownership.json rebased after copy
- `S08` uncontended 12-way run: 810.52s, 4414 passed, ZERO worker crashes (was 4 under CI contention); supports resource exhaustion over any test-specific cause
