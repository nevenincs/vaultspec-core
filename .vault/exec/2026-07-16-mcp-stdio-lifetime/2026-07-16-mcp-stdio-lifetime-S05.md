---
tags:
  - '#exec'
  - '#mcp-stdio-lifetime'
date: '2026-07-16'
modified: '2026-07-16'
step_id: 'S05'
related:
  - "[[2026-07-16-mcp-stdio-lifetime-plan]]"
---

# Add end-to-end orphan test spawning the real MCP server through an intermediary client, killing the client while a sibling holds the pipe, asserting server exit

## Scope

- `tests/unit/mcp_server/test_watchdog.py`

## Description

- Add end-to-end test: a client process creates the server's stdin pipe with an inheritable write end, spawns the real `vaultspec_core.mcp_server.app` module, and leaks the write end into a sibling sleeper
- Kill the client; assert the server exits within 30s while the sibling still holds the pipe (stdin EOF impossible, watchdog is the only reaper)
- Observe server liveness through `OpenProcess`/`WaitForSingleObject` (never `os.kill(pid, 0)`, which terminates on Windows)

## Outcome

The issue-220 field scenario reproduces and resolves in-test; committed with
S04 as `065f3b35`.

## Notes

None.
