---
tags:
  - '#exec'
  - '#test-provisioning-economics'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:83478d7ec752882e0ae75b4d286006df0bb058c14c5a9253c17ef71af7ab2ef8'
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
- `S12` `M` `conftest.py`
- `S12` `verify:` `pytest dev/guards` -> `pass`
- `S13` `M` `conftest.py`
- `S13` `verify:` `just test-broad` -> `fail`
- `S07` `M` `dev/toolchain.py`
- `S07` `verify:` `just test-broad` -> `fail`
- `S09` `M` `dev/toolchain.py`
- `S09` `verify:` `just test-broad` -> `fail`
- `S12` `M` `pyproject.toml`
- `S12` `M` `dev/guards/test_automation_contracts.py`
- `S13` `M` `src/vaultspec_core/mcp_server/tests/test_watchdog.py`

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
- `S12` NOT DONE: a setup-phase deadline was attempted twice (pytest_fixture_setup hookwrapper; faulthandler alarm on the runtest phase hooks) and both corrupt pytest fixture bookkeeping - 133 guards pass without, 138 error with. Reverted; conftest carries a comment recording both dead ends. Exposure reduced by P02 (slowest setup now ~27s, was 6m).
- `S13` NOT DONE, deliberately: after P01/P02/P04 the watchdog tests no longer appear in the lane's 15 slowest entries, so deriving their sleep windows would be churn on the suite's most delicate process-lifecycle tests for no measurable gain. The finding stays recorded in the audit.
- `S07` cause: not reproducible off the contended machine. Three subsequent 12-way runs on an idle box produced zero node-down events (4404, 4414, 4421 passed); the only run with crashes was the one sharing the host with an active CI job at 100% CPU. Resource exhaustion, not a test defect - the watchdog theory stays retracted.
- `S09` no containment written: S07 found nothing test-specific to contain, and an xdist_group applied to the watchdog cohort on a retracted theory would have been a fix for a defect that does not exist
