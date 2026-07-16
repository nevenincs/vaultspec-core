---
tags:
  - '#adr'
  - '#mcp-stdio-lifetime'
date: '2026-07-16'
modified: '2026-07-16'
related:
  - "[[2026-07-16-mcp-stdio-lifetime-research]]"
---

# `mcp-stdio-lifetime` adr: `windows client-pid watchdog for the stdio server` | (**status:** `accepted`)

## Problem Statement

The stdio MCP server's only shutdown path is stdin EOF, and on Windows that
signal is unreliable under real MCP clients: inherited pipe handles keep the
stdin pipe open across client restarts and deaths, so server chains accumulate
indefinitely (`2026-07-16-mcp-stdio-lifetime-research`, upstream report
https://github.com/nevenincs/vaultspec-core/issues/220). The leak degrades the
host materially, so the server needs a second, client-anchored shutdown signal
now.

## Considerations

- Stdin EOF shutdown already works when the pipe actually closes; the fix must
  add a backstop, not replace the transport
  (`2026-07-16-mcp-stdio-lifetime-research`).
- Wrapper chains (`uv.exe`, venv launcher) sit between client and worker, so
  the immediate parent PID identifies the wrong process
  (`2026-07-16-mcp-stdio-lifetime-research`).
- The stdin pipe's creating process is recoverable from the handle itself via
  `GetNamedPipeServerProcessId`, which works for anonymous pipes
  (`2026-07-16-mcp-stdio-lifetime-research`).
- POSIX delivers EOF reliably on process death; the gap is Windows-only.
- `pywin32` must not become a load-bearing dependency: upstream `mcp` is
  actively removing its eager `pywin32` import
  (https://github.com/modelcontextprotocol/python-sdk/pull/2365), so the
  watchdog must use only the standard library.
- The identical defect exists in vaultspec-rag's `vaultspec-search-mcp`; that
  repo decides its own mechanism in its own record, so this decision binds
  only the shared backstop contract, not the sibling's implementation.

## Considered options

- **Client-PID watchdog (chosen).** Resolve the stdin pipe creator, hold a
  `SYNCHRONIZE` handle, wait on it in a daemon thread, hard-exit when
  signaled. Anchors lifetime to the actual client regardless of wrapper depth
  or leaked pipe handles.
- **Parent-PID (`getppid`) watchdog.** Rejected: the immediate parent is the
  `uv`/launcher wrapper, alive in every audited leak.
- **Ancestor-chain walking.** Rejected: racy (PID reuse), fragile across
  launch paths, and still guesses which ancestor is the client.
- **Idle timeout.** Rejected for now: kills long-lived quiet sessions or waits
  hours to reap, and the watchdog already covers every server-side-reachable
  case; may be revisited as an opt-in if client-side pipe leaks prove chronic.
- **Fix the clients.** Out of our control (Claude Code, Codex spawn with full
  handle inheritance); at best a parallel upstream conversation.

## Constraints

- Win32 API access is via `ctypes.windll` only; no new dependency. The three
  calls used (`GetNamedPipeServerProcessId`, `OpenProcess`,
  `WaitForSingleObject`) are stable, documented APIs available on every
  supported Windows version.
- The watchdog must fail open: stdin not a pipe (interactive/console runs),
  an inaccessible client process, or a missing API skips arming and leaves the
  EOF path as-is. Arming failures must never prevent the server from serving.
- Exit from the watchdog thread must not depend on the anyio event loop
  cooperating mid-teardown; a hard `os._exit(0)` is the contract.
- Generations orphaned by a still-alive client remain unreachable until that
  client exits (`2026-07-16-mcp-stdio-lifetime-research`); accepted residual.

## Implementation

A new module in the MCP server package owns the mechanism: a resolver that
maps the process's real stdin handle to the pipe-creating PID, and an arming
function that opens that PID with `SYNCHRONIZE` access, spawns a daemon thread
blocking on `WaitForSingleObject(INFINITE)`, and calls `os._exit(0)` when the
handle signals. The server entrypoint arms the watchdog immediately before
starting the stdio transport, on Windows only; every failure path logs to
stderr at debug level and falls back to EOF-only behavior. Non-Windows
platforms never touch the module's Win32 surface. vaultspec-rag closes the
same defect for `vaultspec-search-mcp` under its own decision record, which
settled on an ancestor-chain watchdog; the repos share the backstop contract
(hard-exit daemon thread, fail-open, EOF path untouched), not the module.

## Rationale

The client-PID watchdog is the only option that fires on the correct process
in every audited failure pattern: dead-ancestor chains and multi-generation
reconnect accumulation both reduce to "the client is gone but the pipe is
still open", and waiting on the pipe creator's process handle detects exactly
that, independent of wrapper depth and inherited handles
(`2026-07-16-mcp-stdio-lifetime-research`). It composes with, rather than
replaces, the working EOF path, costs one blocked daemon thread, and needs no
new dependency.

## Consequences

- Server chains reap themselves when their client dies, on every launch path
  (`uv run`, `uvx`, venv python); wrapper processes unwind for free once the
  worker exits.
- A blocked daemon thread and two retained Win32 handles per server process;
  negligible.
- `os._exit` skips lifespan teardown; acceptable because the lifespan is a
  no-op today, and a future lifespan with real teardown must account for the
  watchdog path.
- Servers whose client is alive but leaked their pipe are reaped only at that
  client's exit; a host-side sweep remains the remedy for chains predating the
  fix.
- vaultspec-rag closes the sibling report under its own decision record; the
  two repos converge on the backstop contract while differing in mechanism.
