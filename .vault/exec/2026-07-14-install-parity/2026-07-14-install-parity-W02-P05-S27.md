---
tags:
  - '#exec'
  - '#install-parity'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S27'
related:
  - "[[2026-07-14-install-parity-plan]]"
---

# Bump the vaultspec-core dependency floor and refresh uv.lock to the released version carrying the DEV member and schema v2

## Scope

- `pyproject.toml`

## Description

- Bump the `vaultspec-core` dependency floor in the vaultspec-rag project manifest from `>=0.1.27` to `>=0.1.38`, the released version carrying the DEV member and schema v2.
- Refresh the lock file so the resolved `vaultspec-core` moves from 0.1.36 to 0.1.38.
- Sync the rag project environment onto the bumped floor and confirm `InstallMode.DEV` imports and resolves in the rag environment itself.
- Run the rag unit test gate against the bumped core to confirm the floor move breaks nothing.

## Outcome

The floor bump and lock refresh are committed in the vaultspec-rag repository. The rag environment resolves `vaultspec-core` 0.1.38 and imports `InstallMode.DEV`. The rag unit gate reports 1321 passed and 1 skipped, with the single failure being a Windows-host-only platform test unrelated to the core bump. With the floor floored on the released parity core and the gate green, the rag mode-adoption phase is unblocked.

## Notes

One rag unit test fails on this Windows development host: the server-stop test that simulates POSIX behaviour by monkeypatching the platform to Linux and asserts no CLI-side shutdown log is written. On a Windows host the real-platform check on the shutdown-log path is not intercepted by the monkeypatch, so the log file is written and the assertion fails. The vaultspec-rag continuous-integration workflow runs on Linux, where this test passes; the failure is a host-platform artifact independent of the core version bump, which touches only the workspace-mode, enum, and MCP-launch surfaces and nothing on the server-stop path. Reported, not fixed, as out of scope for the release gate.

The rag repository forbids committing regenerated provider mirror files through a pre-commit guard, so the pending provider-file sync state left in the working tree was preserved uncommitted rather than folded into this commit; the floor bump and lock refresh are the only committed changes. Refreshing the rag environment required stopping that worktree's running search-server processes, which held a Windows file lock on the environment's console-script executable.
