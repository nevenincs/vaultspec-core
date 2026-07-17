---
tags:
  - '#plan'
  - '#mcp-stdio-lifetime'
date: '2026-07-17'
modified: '2026-07-17'
tier: L2
related:
  - '[[2026-07-16-mcp-stdio-lifetime-adr]]'
  - '[[2026-07-16-mcp-stdio-lifetime-research]]'
---

# `mcp-stdio-lifetime` plan

## Steps

### Phase `P01` - watchdog engine parity

Bring the watchdog module to the shared cross-repo contract: kill switch, structured telemetry, ancestor-chain fallback, POSIX poll, and the entrypoint override.

- [x] `P01.S01` - Open feature branch and draft PR referencing issue 220 and the parity revision; `repo workflow`.
- [x] `P01.S02` - Add VAULTSPEC_STDIO_WATCHDOG kill switch honored before any arming, with off values matching the sibling repo; `src/vaultspec_core/mcp_server/watchdog.py`.
- [x] `P01.S03` - Emit one structured JSON exit event to stderr before every hard exit, shared by all anchors; `src/vaultspec_core/mcp_server/watchdog.py`.
- [x] `P01.S04` - Add PID-reuse-safe ancestor-chain fallback armed when stdin pipe resolution declines: startup handles, creation-time monotonicity, grace-window pruning, wait-any; `src/vaultspec_core/mcp_server/watchdog.py`.
- [x] `P01.S05` - Add POSIX coarse reparent poll exiting on orphaning or explicit client death; `src/vaultspec_core/mcp_server/watchdog.py`.
- [x] `P01.S06` - Add --parent-pid entrypoint option watched ahead of discovery and wire arming outcomes through \_serve logging; `src/vaultspec_core/mcp_server/app.py`.

### Phase `P02` - real-process test parity

Prove every new anchor and knob with real processes and pipes, updating the tests whose semantics the fallback changes.

- [x] `P02.S07` - Add kill-switch and parent-pid override tests driving real worker subprocesses; `tests/unit/mcp_server/test_watchdog.py`.
- [x] `P02.S08` - Rework the non-pipe stdin test for fallback semantics and add ancestor-death and grace-window fallback tests with real process chains; `tests/unit/mcp_server/test_watchdog.py`.
- [x] `P02.S09` - Add POSIX-contract assertions for the reparent poll and explicit-pid path exercised on the current platform honestly; `tests/unit/mcp_server/test_watchdog.py`.

### Phase `P03` - documentation and gates

Document the contract and knobs, register the env var, and run the full gate set through review to a ready PR.

- [x] `P03.S10` - Document the watchdog contract and knobs in the MCP doc and register VAULTSPEC_STDIO_WATCHDOG in the CLI reference env table via the builtins source; `docs/MCP.md`.
- [ ] `P03.S11` - Run gates, dispatch code review, resolve findings, append audit entries, finalize PR; `quality gates`.

## Description

Execute the 2026-07-17 parity revision of 2026-07-16-mcp-stdio-lifetime-adr:
bring core's stdio watchdog to the cross-repo backstop and operability
contract the sibling repo shipped, keeping the client-PID pipe-creator as the
precise primary anchor. New surface: the VAULTSPEC_STDIO_WATCHDOG kill
switch, structured JSON exit telemetry, a PID-reuse-safe ancestor-chain
fallback for non-pipe launches, a POSIX coarse reparent poll, a --parent-pid
entrypoint override, and user documentation of the contract. Grounded by the
cross-repo parity delta in 2026-07-16-mcp-stdio-lifetime-research; the
rag-side half of the convergence is tracked as rag issue 229.

## Parallelization

Phases are sequential: P02's tests exercise P01's engine, and P03 gates the
finished set. Within P01, S02 through S05 are independent module additions
and may interleave, but S06 (wiring) lands last; within P02 the three test
steps are independent.

## Verification

- Kill-switch, override, fallback ancestor-death, grace-window, and POSIX
  contract tests all pass with real processes; the original client-PID e2e
  orphan test still passes unchanged.
- Behavior parity with the sibling repo's shipped contract is
  point-for-point: disable values, override precedence, telemetry event
  shape, fail-open discipline.
- prek clean on changed files; ty clean on both Windows and linux platform
  assumptions; CI-matching unit gate and the MCP suites green; dependency
  audit clean.
- Code review dispatched and findings resolved; audit entries appended; PR
  references issue 220 and rag issue 229 and is marked ready for review.
