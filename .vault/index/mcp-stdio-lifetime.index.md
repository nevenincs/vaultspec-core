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
  - '[[2026-07-17-mcp-stdio-lifetime-P01-S01]]'
  - '[[2026-07-17-mcp-stdio-lifetime-P01-S02]]'
  - '[[2026-07-17-mcp-stdio-lifetime-P01-S03]]'
  - '[[2026-07-17-mcp-stdio-lifetime-P01-S04]]'
  - '[[2026-07-17-mcp-stdio-lifetime-P01-S05]]'
  - '[[2026-07-17-mcp-stdio-lifetime-P01-S06]]'
  - '[[2026-07-17-mcp-stdio-lifetime-P02-S07]]'
  - '[[2026-07-17-mcp-stdio-lifetime-P02-S08]]'
  - '[[2026-07-17-mcp-stdio-lifetime-P02-S09]]'
  - '[[2026-07-17-mcp-stdio-lifetime-P03-S10]]'
  - '[[2026-07-17-mcp-stdio-lifetime-P03-S11]]'
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
- `2026-07-17-mcp-stdio-lifetime-P01-S01` - Open feature branch and draft PR referencing issue 220 and the parity revision
- `2026-07-17-mcp-stdio-lifetime-P01-S02` - Add VAULTSPEC_STDIO_WATCHDOG kill switch honored before any arming, with off values matching the sibling repo
- `2026-07-17-mcp-stdio-lifetime-P01-S03` - Emit one structured JSON exit event to stderr before every hard exit, shared by all anchors
- `2026-07-17-mcp-stdio-lifetime-P01-S04` - Add PID-reuse-safe ancestor-chain fallback armed when stdin pipe resolution declines: startup handles, creation-time monotonicity, grace-window pruning, wait-any
- `2026-07-17-mcp-stdio-lifetime-P01-S05` - Add POSIX coarse reparent poll exiting on orphaning or explicit client death
- `2026-07-17-mcp-stdio-lifetime-P01-S06` - Add --parent-pid entrypoint option watched ahead of discovery and wire arming outcomes through \_serve logging
- `2026-07-17-mcp-stdio-lifetime-P02-S07` - Add kill-switch and parent-pid override tests driving real worker subprocesses
- `2026-07-17-mcp-stdio-lifetime-P02-S08` - Rework the non-pipe stdin test for fallback semantics and add ancestor-death and grace-window fallback tests with real process chains
- `2026-07-17-mcp-stdio-lifetime-P02-S09` - Add POSIX-contract assertions for the reparent poll and explicit-pid path exercised on the current platform honestly
- `2026-07-17-mcp-stdio-lifetime-P03-S10` - Document the watchdog contract and knobs in the MCP doc and register VAULTSPEC_STDIO_WATCHDOG in the CLI reference env table via the builtins source
- `2026-07-17-mcp-stdio-lifetime-P03-S11` - Run gates, dispatch code review, resolve findings, append audit entries, finalize PR

### plan

- `2026-07-16-mcp-stdio-lifetime-plan` - `mcp-stdio-lifetime` plan
- `2026-07-17-mcp-stdio-lifetime-plan` - `mcp-stdio-lifetime` plan

### research

- `2026-07-16-mcp-stdio-lifetime-research` - `mcp-stdio-lifetime` research: `stdio server lifetime and orphan accumulation on Windows`
