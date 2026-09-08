---
tags:
  - '#exec'
  - '#test-provisioning-economics'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:03b7c93b116d923431f063cfae58f759e0ec6192cb3a1b9412273b8c13ad25ea'
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
- `S07` `M` `conftest.py`
- `S07` `M` `pyproject.toml`
- `S07` `M` `src/vaultspec_core/vaultcore/tests/test_fix_writer_concurrency.py`
- `S07` `verify:` `pytest test_fix_writer_concurrency.py::test_concurrent_edit_survives_an_annotations_fix_pass x20` -> `pass`
- `S10` `M` `dev/toolchain.py`
- `S10` `verify:` `just test-broad` -> `fail`
- `S11` `M` `dev/toolchain.py`
- `S11` `verify:` `just test-broad` -> `fail`

## Notes

- `S01` 236 passed in 197.93s; setup median fell from ~20s to ~2s
- `S02` guard found a pre-existing production violation in cli/\_target.py; filed as #515, allowlisted with a staleness check rather than silently exempted
- `S03` boundary measured: 236-test file 197.93s against a pre-change run still incomplete at 20min under equal load
- `S04` session template plus per-test clone
- `S05` session template plus per-test clone
- `S06` install() itself serves the default shape from a per-process template, covering all ~300 call sites; mcp-ownership.json rebased after copy
- `S08` uncontended 12-way run: 810.52s, 4414 passed, ZERO worker crashes (was 4 under CI contention); supports resource exhaustion over any test-specific cause
- `S07` the 4 crashes did not recur on an uncontended machine; separately, the boundary WAS observable in one cohort (4/20 fail suppressed, 0/20 restored, 0/20 with the durable marker)
- `S10` broad, harness and repo lanes now pass -n auto --dist loadfile; loadfile keeps a module on one worker so the session template is built once per worker not once per test
- `S11` 9m03s against the 36-46min headline, zero worker crashes; the single failure is issue 518, pre-existing and reproduced on b5c7f256 under the same env
