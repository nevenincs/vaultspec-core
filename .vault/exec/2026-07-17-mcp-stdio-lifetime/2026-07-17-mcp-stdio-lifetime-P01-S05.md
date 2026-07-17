---
tags:
  - '#exec'
  - '#mcp-stdio-lifetime'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S05'
related:
  - "[[2026-07-17-mcp-stdio-lifetime-plan]]"
---

# Add POSIX coarse reparent poll exiting on orphaning or explicit client death

## Scope

- `src/vaultspec_core/mcp_server/watchdog.py`

## Description

- Add `_posix_watchdog` coarse reparent poll with explicit-pid liveness checks
- Arm it on non-Windows platforms behind the same kill switch and fail-open guard

## Outcome

POSIX arming now returns True (was a hard no-op); committed as `7659724d`.

## Notes

POSIX liveness probes use `os.kill(pid, 0)` which is POSIX-only semantics by design.
