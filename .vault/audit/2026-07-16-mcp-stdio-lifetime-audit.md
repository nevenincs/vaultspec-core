---
tags:
  - '#audit'
  - '#mcp-stdio-lifetime'
date: '2026-07-16'
modified: '2026-07-16'
related:
  - "[[2026-07-16-mcp-stdio-lifetime-plan]]"
  - "[[2026-07-16-mcp-stdio-lifetime-adr]]"
---

# `mcp-stdio-lifetime` audit: `client-pid watchdog review`

## Scope

Branch review of the Windows client-PID stdio watchdog (four code commits vs
main): `src/vaultspec_core/mcp_server/watchdog.py`, its wiring in
`src/vaultspec_core/mcp_server/app.py`, the real-process test suite
`tests/unit/mcp_server/test_watchdog.py`, and the three latent test repairs
the temp-shim fix surfaced. Reviewed by the code-reviewer persona against the
governing ADR and plan for safety, Win32 correctness, `os._exit` semantics,
the code-stands-alone boundary, test integrity, and conventions.

## Findings

### fail-open-gap | high | Two narrow startup paths could raise instead of failing open

`resolve_stdin_client_pid` guarded only `OSError` around the handle lookup:
a console-less launch (`sys.stdin is None`) or a Windows build lacking the
`GetNamedPipeServerProcessId` export would raise `AttributeError` through
`_serve` and abort the server, violating the decision's "arming failures
must never prevent serving" constraint. Practically unreachable under the
documented stdio launch paths, but a named contract. RESOLVED: resolver and
arming bodies now wrap in broad exception guards that log at debug and
decline.

### undeclared-argtypes | medium | Foreign functions relied on default int inference

Only `OpenProcess.restype` was declared; `GetNamedPipeServerProcessId`,
`WaitForSingleObject`, and `CloseHandle` marshalled through ctypes defaults,
which fail silently when they drift. RESOLVED: `_kernel32` now declares
`argtypes` and `restype` for every binding.

### wait-failed-handle | low | Failed wait path leaked the process handle

A non-signal return from `WaitForSingleObject` logged and left the
`SYNCHRONIZE` handle open for the process lifetime. RESOLVED: the thread now
closes the handle on the no-signal path.

### shutdown-log-level | low | Shutdown breadcrumb logged below the lastResort threshold

The client-exited line logged at info, which the stdlib lastResort handler
drops; the one observable trace of a watchdog-initiated exit could vanish.
RESOLVED: raised to warning.

### cosmetic-platform-branch | low | In-process contract test branched identically per platform

Both branches asserted the same contract, reading as a behavioral split that
does not exist. RESOLVED: collapsed to unconditional asserts.

### linux-ty-windll | medium | kernel32 loader failed type resolution on the linux CI runner

Local ty (Windows host) resolved `ctypes.WinDLL` fine, but the CI runner's
platform assumption rejected it: the loader body carried no platform
narrowing of its own, only its callers did. RESOLVED: the loader now
narrows on `sys.platform` and raises off Windows; ty passes on both
platform assumptions.

### mcp-websocket-cve | medium | Locked mcp 1.28.0 tripped the dependency audit

A fresh upstream advisory (WebSocket server transport missing Host/Origin
validation, patched in `mcp@1.28.1`) began failing the audit gate; the
vulnerable transport is unused here (stdio only) but the gate is version-
based. RESOLVED: dependency floor raised to `mcp>=1.28.1` and the lock
upgraded; audit reports clean.

### pid-reuse-window | low | Microsecond PID-reuse window between resolve and open

If the client dies and its PID recycles between resolution and
`OpenProcess`, the watchdog anchors to the wrong process. ACCEPTED: matches
the decision's accepted residual; the window is microseconds at server
spawn, when the client is by definition alive.

### parity-dedup-handle-leak | medium | Deduped fallback ancestors leaked their opened handles

In the 2026-07-17 parity revision, when an explicit parent override was
also a discovered ancestor and the fallback engaged, the duplicate's
freshly opened `SYNCHRONIZE` handle was dropped without `CloseHandle` -
the sibling implementation dedups inside the walk and closes duplicates.
RESOLVED: duplicates are now closed at the dedup site.

### parity-thread-start-leak | low | Thread-start failure left opened handles behind

An arming-thread start failure failed open correctly but unwound past the
watched handle set without closing it. RESOLVED: the start is wrapped and
every handle closes before the fail-open guard absorbs the error.

### parity-kill-switch-test-nit | low | Kill-switch test asserted an environment-incidental resolver result

The in-process kill-switch test asserted the resolver's `None` under
the disabled env, which the switch does not govern; under a harness that
pipes stdin into the test runner it could flake. RESOLVED: the assertion
was dropped; the switch is proven by the disable predicate and the arming
refusal.

## Recommendations

- Ship after the resolved findings above; verdict PASS-with-notes, no
  revision cycle required beyond the applied fixes.
- Sweep `tests/unit/mcp_server/test_tool_surface.py` docstrings for
  pre-existing decision-record citations (out of this branch's scope) in a
  future code-stands-alone pass.
- The sibling defect in vaultspec-rag is governed and audited in that repo's
  own records; no core follow-up beyond the shared backstop contract.
