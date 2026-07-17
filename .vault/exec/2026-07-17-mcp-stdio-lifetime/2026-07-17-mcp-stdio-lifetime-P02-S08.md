---
tags:
  - '#exec'
  - '#mcp-stdio-lifetime'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S08'
related:
  - "[[2026-07-17-mcp-stdio-lifetime-plan]]"
---

# Rework the non-pipe stdin test for fallback semantics and add ancestor-death and grace-window fallback tests with real process chains

## Scope

- `tests/unit/mcp_server/test_watchdog.py`

## Description

- Rework the non-pipe stdin test: resolution declines, arming now succeeds via fallback on every platform
- Add ancestor-death fallback test through a real intermediary chain (short grace)
- Add grace-window pruning test reporting through a result file so a dead parent's pipe cannot fake the outcome

## Outcome

Committed as `e6737158`.

## Notes

Both pre-existing e2e server tests were passing vacuously: the standalone server refuses a bare cwd, so the server under test had been crashing at boot. They now scaffold the minimal workspace and assert liveness before the kill.
