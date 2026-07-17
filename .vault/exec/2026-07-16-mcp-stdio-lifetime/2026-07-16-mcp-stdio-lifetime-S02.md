---
tags:
  - '#exec'
  - '#mcp-stdio-lifetime'
date: '2026-07-16'
modified: '2026-07-16'
step_id: 'S02'
related:
  - "[[2026-07-16-mcp-stdio-lifetime-plan]]"
---

# Implement stdin-pipe client-PID resolver via ctypes GetNamedPipeServerProcessId and arm_client_watchdog with SYNCHRONIZE wait thread and hard exit, fail-open on every error path, POSIX no-op

## Scope

- `src/vaultspec_core/mcp_server/watchdog.py`

## Description

- Add `resolve_stdin_client_pid` mapping the stdin OS handle to its pipe-creating PID via ctypes `GetNamedPipeServerProcessId`
- Add `arm_client_watchdog` opening the client with `SYNCHRONIZE`, waiting in a daemon thread, hard-exiting via `os._exit(0)` on signal
- Add `_kernel32` loader with `use_last_error` and an explicit `OpenProcess` restype (`c_void_p`; the ctypes default truncates 64-bit handles)
- Accept an explicit `client_pid` override; fail open on every error path; return `None`/`False` unconditionally off Windows

## Outcome

`src/vaultspec_core/mcp_server/watchdog.py` committed as `fd57e0c5`; ruff and
ty clean.

## Notes

None.
