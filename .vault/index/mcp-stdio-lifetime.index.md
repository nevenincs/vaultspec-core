---
generated: true
tags:
  - '#index'
  - '#mcp-stdio-lifetime'
date: '2026-07-17'
modified: '2026-07-17'
related:
  - '[[2026-07-16-mcp-stdio-lifetime-S01]]'
  - '[[2026-07-16-mcp-stdio-lifetime-S02]]'
  - '[[2026-07-16-mcp-stdio-lifetime-S03]]'
  - '[[2026-07-16-mcp-stdio-lifetime-S04]]'
  - '[[2026-07-16-mcp-stdio-lifetime-S05]]'
  - '[[2026-07-16-mcp-stdio-lifetime-S06]]'
  - '[[2026-07-16-mcp-stdio-lifetime-adr]]'
  - '[[2026-07-16-mcp-stdio-lifetime-audit]]'
  - '[[2026-07-16-mcp-stdio-lifetime-plan]]'
  - '[[2026-07-16-mcp-stdio-lifetime-research]]'
  - '[[2026-07-17-mcp-stdio-lifetime-plan]]'
---

# `mcp-stdio-lifetime` feature index

Auto-generated index of all documents tagged with `#mcp-stdio-lifetime`.

## Documents

### adr

- `2026-07-16-mcp-stdio-lifetime-adr` - `mcp-stdio-lifetime` adr: `windows client-pid watchdog for the stdio server` | (**status:** `accepted`)

### audit

- `2026-07-16-mcp-stdio-lifetime-audit` - `mcp-stdio-lifetime` audit: `client-pid watchdog review`

### exec

- `2026-07-16-mcp-stdio-lifetime-S01` - Open feature branch and draft PR referencing issue 220 with the plan summary as body
- `2026-07-16-mcp-stdio-lifetime-S02` - Implement stdin-pipe client-PID resolver via ctypes GetNamedPipeServerProcessId and arm_client_watchdog with SYNCHRONIZE wait thread and hard exit, fail-open on every error path, POSIX no-op
- `2026-07-16-mcp-stdio-lifetime-S03` - Wire arm_client_watchdog into \_serve immediately before mcp.run with stderr debug logging of armed or skipped outcome
- `2026-07-16-mcp-stdio-lifetime-S04` - Add real-pipe resolver test, real-process watchdog exit test, and fail-open tests for console stdin and dead client PID
- `2026-07-16-mcp-stdio-lifetime-S05` - Add end-to-end orphan test spawning the real MCP server through an intermediary client, killing the client while a sibling holds the pipe, asserting server exit
- `2026-07-16-mcp-stdio-lifetime-S06` - Run prek, ty, and unit pytest gates, fix findings, finalize PR body and mark ready for review

### plan

- `2026-07-16-mcp-stdio-lifetime-plan` - `mcp-stdio-lifetime` plan
- `2026-07-17-mcp-stdio-lifetime-plan` - `mcp-stdio-lifetime` plan

### research

- `2026-07-16-mcp-stdio-lifetime-research` - `mcp-stdio-lifetime` research: `stdio server lifetime and orphan accumulation on Windows`
