---
tags:
  - '#research'
  - '#mcp-testing'
date: '2026-07-17'
modified: '2026-07-17'
related:
  - "[[2026-02-22-mcp-testing-adr]]"
---

# `mcp-testing` research: `functional assertion floor inventory`

Which MCP-server tests in vaultspec-core and vaultspec-rag assert served
functionality, and which assert only process existence? The operator's
standard is that a spawned server must prove measurable capability - a
correct handshake, the expected tool surface, a correct command result -
not merely that a process booted, stayed alive, or exited. The inventory
found the in-memory and one core wire-level suite already functional, and
exactly one class of offender in each repo: the lifecycle end-to-end tests
that spawn the real server and assert nothing about serving.

## Findings

### vaultspec-core: the wire-level and in-memory suites are functional

`tests/mcp/test_mcp_stdio_e2e.py` drives the real spawned server through
the `mcp` SDK's `stdio_client` and a real `ClientSession`: it asserts the
`initialize` result's server name, the exact nine-tool surface with output
schemas, a `status` call returning a rollup payload, an `invoke`
round-trip's `ok`/`exit_code`/`command`, and denylist rejection.
`tests/unit/mcp_server/` (66 tests) exercises every tool through the
in-memory session transport with payload assertions per
`2026-02-22-mcp-testing-adr`. `tests/mcp/test_mcp_entrypoint.py` asserts
stdout protocol hygiene and EOF exit; `tests/mcp/test_mcp_context_budget.py`
measures real serialized definitions.

### vaultspec-core: the watchdog lifecycle e2es assert liveness only

The two watchdog end-to-end tests in
`tests/unit/mcp_server/test_watchdog.py` (leaked-pipe orphan reap;
`--parent-pid` override reap) spawn the real server but assert only boot
liveness and exit. Nothing distinguishes "a process that will serve" from
"a process wedged after arming": the lifecycle claim rests on an unproven
serving assumption. A functional precondition (handshake completed, nine
tools listed) is expressible in both: the flag test owns the server's
pipes directly, and the leaked-pipe test's client script can perform the
newline-delimited JSON-RPC exchange itself before the kill.

### vaultspec-rag: functional assertions exist but never cross the wire

`test_mcp_conformance_surface.py` asserts the exact five-tool surface,
read-only annotations, schema defaults, and output schemas - all via
in-process `mcp.list_tools()`. `test_mcp_no_local_fallback.py` drives each
tool coroutine directly and asserts exact degraded-mode errors. No rag
test performs an `initialize`/`tools/list`/tool-call exchange against a
spawned `vaultspec-search-mcp` subprocess over its actual stdio transport.

### vaultspec-rag: both stdio-lifetime e2es are liveness only

`test_stdio_lifetime_e2e.py::test_worker_reaps_itself_when_an_ancestor_dies`
uses a synthetic watchdog-only worker that never touches MCP.
`test_stdin_eof_still_exits_the_real_shim_cleanly` spawns the real shim,
writes zero bytes to its stdin, reads nothing from its stdout, sleeps 5s
on an unverified "reached the read loop" assumption, and asserts only
`returncode == 0`. Neither proves the shim serves.

### Sweep context

The core offenders live on the watchdog-parity branch (PR 223), so the fix
stacks on it. The rag worktree is mid-flight in another session (branch
`chore/prerelease-maintenance`), so the rag half is handed to that repo's
board alongside its open parity items. Not investigated: HTTP daemon-mode
serving assertions in rag (`test_service_eviction.py` covers the REST
routes directly).

## Sources

- `tests/mcp/test_mcp_stdio_e2e.py:74` (`_drive_session`, the functional wire template)
- `tests/unit/mcp_server/test_watchdog.py` (leaked-pipe and parent-pid e2es, branch feat/mcp-watchdog-parity)
- `tests/mcp/test_mcp_entrypoint.py:42`
- rag `src/vaultspec_rag/tests/test_mcp_conformance_surface.py:61`
- rag `src/vaultspec_rag/tests/test_mcp_no_local_fallback.py:105`
- rag `src/vaultspec_rag/tests/integration/test_stdio_lifetime_e2e.py:71` and `:115` (at rag main `6ee6f8f` lineage)
- Operator directive of 2026-07-17: functional capability, not existence, is the pass criterion for a running MCP service
