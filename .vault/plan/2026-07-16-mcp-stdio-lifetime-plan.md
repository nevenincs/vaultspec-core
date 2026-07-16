---
tags:
  - '#plan'
  - '#mcp-stdio-lifetime'
date: '2026-07-16'
modified: '2026-07-17'
tier: L1
related:
  - '[[2026-07-16-mcp-stdio-lifetime-adr]]'
  - '[[2026-07-16-mcp-stdio-lifetime-research]]'
---

# `mcp-stdio-lifetime` plan

- [ ] `S01` - Open feature branch and draft PR referencing issue 220 with the plan summary as body; `repo workflow`.
- [ ] `S02` - Implement stdin-pipe client-PID resolver via ctypes GetNamedPipeServerProcessId and arm_client_watchdog with SYNCHRONIZE wait thread and hard exit, fail-open on every error path, POSIX no-op; `src/vaultspec_core/mcp_server/watchdog.py`.
- [ ] `S03` - Wire arm_client_watchdog into \_serve immediately before mcp.run with stderr debug logging of armed or skipped outcome; `src/vaultspec_core/mcp_server/app.py`.
- [ ] `S04` - Add real-pipe resolver test, real-process watchdog exit test, and fail-open tests for console stdin and dead client PID; `tests/unit/mcp_server/test_watchdog.py`.
- [ ] `S05` - Add end-to-end orphan test spawning the real MCP server through an intermediary client, killing the client while a sibling holds the pipe, asserting server exit; `tests/unit/mcp_server/test_watchdog.py`.
- [ ] `S06` - Run prek, ty, and unit pytest gates, fix findings, finalize PR body and mark ready for review; `quality gates`.

## Description

Execute the accepted 2026-07-16-mcp-stdio-lifetime-adr: give the stdio MCP
server a Windows-only client-PID watchdog so server chains exit when their
spawning client dies, closing the orphan accumulation reported in issue 220.
A new module resolves the stdin pipe's creating process and waits on its
handle in a daemon thread (ctypes only, fail-open); the server entrypoint arms
it just before starting the stdio transport. Real-process tests prove the
resolver, the exit path, the fail-open paths, and the end-to-end orphan
scenario the research reproduced.

## Steps

## Parallelization

Strictly sequential: S01 opens the branch and draft PR, S02 must land before
S03 (wiring imports the module), S04 and S05 depend on S02/S03, and S06 gates
the finished set. The plan is small enough that parallel dispatch buys
nothing.

## Verification

- The end-to-end orphan test reproduces the issue-220 scenario (client killed
  while a sibling holds the pipe) and the server exits within its timeout.
- Fail-open tests prove console stdin and a dead client PID leave the server
  serving with the watchdog disarmed.
- prek passes on all changed files; ty reports no new diagnostics; the unit
  pytest suites (`tests/unit/mcp_server` and `src/vaultspec_core -m unit`) are
  green.
- The PR references issue 220 and is marked ready for review; every Step row
  is closed via the plan verbs.
