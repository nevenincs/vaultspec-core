---
tags:
  - '#exec'
  - '#mcp-stdio-lifetime'
date: '2026-07-16'
modified: '2026-07-16'
step_id: 'S04'
related:
  - "[[2026-07-16-mcp-stdio-lifetime-plan]]"
---

# Add real-pipe resolver test, real-process watchdog exit test, and fail-open tests for console stdin and dead client PID

## Scope

- `tests/unit/mcp_server/test_watchdog.py`

## Description

- Add resolver tests: pipe creator identified directly and through a wrapper intermediary (real subprocesses, real pipes)
- Add fail-open tests: file-backed stdin declines; in-process platform contract holds
- Add dead-client test: arming against an exited process (handle held) exits the worker immediately
- Repair `tests/_windows_temp_compat.py` to pytest 9.1's `make_numbered_dir_with_cleanup` contract (required `register` kwarg) - the shim had broken every `tmp_path` test under `tests/` on Windows

## Outcome

Five tests green in `tests/unit/mcp_server/test_watchdog.py`; committed as
`065f3b35`. On non-Windows platforms the same tests assert the genuine
fail-open contract instead of being skipped.

## Notes

The dead-client watchdog fires fast enough to beat the worker's own print:
the test asserts on exit code and elapsed time, not output. The shim repair
surfaced three latent test failures previously masked by the broken fixture;
repaired in follow-up commit `ced8e04d` (stale registry-launch expectation
vs the install-mode token contract, a `monkeypatch.chdir`, and the security
suite's `skipif` symlink gate replaced by a capability-honest planting
helper).
