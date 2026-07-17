---
tags:
  - '#research'
  - '#mcp-stdio-lifetime'
date: '2026-07-16'
modified: '2026-07-16'
related: []
---

# `mcp-stdio-lifetime` research: `stdio server lifetime and orphan accumulation on Windows`

Why does the stdio MCP server (`python -m vaultspec_core.mcp_server.app`) outlive
its client on Windows, and what shutdown mechanism would prevent the orphan
accumulation reported in https://github.com/nevenincs/vaultspec-core/issues/220?
Live triage on the reporting host (2026-07-17) confirmed the leak, ruled out the
obvious suspects, and isolated the failure to stdin EOF never arriving; the
evidence favors a client-PID watchdog keyed off the stdin pipe's creating
process.

## Findings

### The leak is real and reproduces at will

A `Win32_Process` sweep on the reporting host found all 8 leaked chains from
issue 220 still live, spanning 2026-07-15 16:30 through 2026-07-16 23:17, each
a `uv.exe -> python.exe -> python.exe` chain. Spawning a server via
`uv run --no-sync python -m vaultspec_core.mcp_server.app`, completing an MCP
`initialize`, then closing the spawner's stdin reproduced the transient state:
the `uv` wrapper exited immediately while the worker python survived it by a
few seconds before exiting.

### Plain stdin-EOF shutdown already works

The same experiment shows the full chain does tear down within seconds of the
stdin pipe actually closing. The `mcp` SDK stdio transport (pinned
`mcp>=1.26.0`, `pyproject.toml:20`) handles EOF correctly, and the wrappers
(`uv.exe`, venv launcher) simply wait on their child, so worker exit propagates
up the chain unaided. The one previously known in-repo hazard - `invoke`
subprocesses inheriting the server's stdin and pinning the pipe - was already
fixed with `stdin=subprocess.DEVNULL` at
`src/vaultspec_core/mcp_server/tools/gateway.py:512`.

### The failure mode is EOF never arriving, via inherited pipe handles

Clients (Claude Code, Codex) spawn each server generation with full handle
inheritance, so generation N inherits the write end of generation N-1's stdin
pipe. An older server can never observe EOF while any younger sibling lives,
and when the client dies the OS closes only the client's own copies - the
inherited copies survive in the sibling chains, which therefore pin each other
alive indefinitely. This matches the audited pattern in issue 220: one Codex
client accumulated three generations across reconnects, none exiting.

### A parent-PID watchdog cannot fix it; a client-PID watchdog can

In every audited chain the worker's immediate parent (`uv.exe`) was alive -
only ancestors above it were dead - so `os.getppid()` watching is useless
under wrapper chains. The stdin pipe itself identifies the true client:
`GetNamedPipeServerProcessId` returns the pipe-creating process for anonymous
pipes too, since Windows implements them over named pipes
(https://learn.microsoft.com/en-us/windows/win32/api/namedpipeapi/nf-namedpipeapi-getnamedpipeserverprocessid).
Opening that PID with `SYNCHRONIZE` access and blocking on
`WaitForSingleObject` in a daemon thread yields a wake-up exactly when the
client terminates, regardless of wrapper depth and regardless of leaked pipe
handles. `os._exit()` from that thread avoids fighting the anyio event loop
during teardown.

### Residual gap and non-Windows behavior

Generations orphaned by a still-alive client that leaked their pipes are
unreachable by any server-side signal; the watchdog reaps them only when that
client eventually exits. An idle timeout was considered and set aside as an
ADR-level trade-off. On POSIX the kernel closes pipe ends on process death and
EOF delivery is reliable, so the watchdog is a Windows-only concern.

### Sibling surface

vaultspec-rag's `vaultspec-search-mcp` stdio entrypoint shows identical
behavior per issue 220; the same mechanism applies. Not investigated: HTTP/SSE
transports (not used by either package's stdio registration).

### Cross-repo parity delta (added 2026-07-17, post-merge)

Both fixes are merged: core's client-PID watchdog
(`src/vaultspec_core/mcp_server/watchdog.py`) and vaultspec-rag's
ancestor-chain watchdog (rag `src/vaultspec_rag/server/_stdio_lifetime.py`,
rag main `6ee6f8f`). Comparing the two, rag carries robustness features core
lacks:

- **Operator kill switch**: `VAULTSPEC_RAG_STDIO_WATCHDOG=0|false|off|no`
  disables the watchdog; core has no disable path. Core's env convention is
  bare `VAULTSPEC_*` (per the CLI reference env table), so the parity name
  is `VAULTSPEC_STDIO_WATCHDOG`.
- **Explicit client override**: rag accepts `--parent-pid` on the shim
  entrypoint, watched ahead of discovery; core's `client_pid` parameter is
  reachable only in code.
- **Coverage when stdin is not a client pipe**: rag's ancestor-chain
  discovery works for any launch shape; core fails open entirely when pipe
  resolution declines (console-less or exotic launches get no backstop).
  Rag's chain walk is PID-reuse safe (handles taken at startup plus
  creation-time monotonicity) and prunes transient spawn helpers with a 10s
  grace window; the trade-off is semantic bluntness - any ancestor's death
  (including a terminal above the client) fires it.
- **POSIX backstop**: rag runs a coarse reparent poll (15s) plus explicit
  parent liveness; core is a strict POSIX no-op on the grounds that EOF
  delivery is reliable there.
- **Structured exit telemetry**: rag emits one JSON event line to stderr
  (`stdio_watchdog_exit` with the dead ancestor pid/exe) before
  `os._exit(0)`; core logs a plain warning line.
- **Documentation**: rag documents the watchdog contract and its knobs in
  its configuration and MCP docs; core's watchdog is undocumented.

Where core is ahead: the pipe-creator anchor identifies the exact client
regardless of wrapper depth (rag fires on above-client ancestor deaths too)
and needs no grace heuristics on the primary path; the ctypes prototypes
are fully declared on both sides.

### Board sweep (2026-07-17)

Open issues: core `#215`, `#213`, `#205` - all covered by open PRs 216-218
awaiting review, none watchdog-scoped (`#215` is MCP-adjacent gitignore
hygiene). vaultspec-rag has zero open issues (`rag#184` closed 2026-07-16).
No board item requires handling inside this parity sweep; the rag-side
parity recommendation (adopting a pipe-creator primary anchor) has no home
yet and would need a new rag issue.

## Sources

- https://github.com/nevenincs/vaultspec-core/issues/220
- `src/vaultspec_core/mcp_server/app.py:107` (`_serve`, sole shutdown path is `mcp.run()`)
- `src/vaultspec_core/mcp_server/tools/gateway.py:512`
- `pyproject.toml:20`
- https://learn.microsoft.com/en-us/windows/win32/api/namedpipeapi/nf-namedpipeapi-getnamedpipeserverprocessid
- Live process audit and EOF experiment, reporting host, 2026-07-17 (transient; not re-fetchable)
- vaultspec-rag `src/vaultspec_rag/server/_stdio_lifetime.py` and `server/_main.py` at rag main `6ee6f8f`
- https://github.com/nevenincs/vaultspec-rag/pull/228
- `src/vaultspec_core/builtins/reference/cli.md:657` (env-var naming convention)
