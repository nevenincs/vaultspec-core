---
tags:
  - '#plan'
  - '#mcp-testing'
date: '2026-07-17'
modified: '2026-07-17'
tier: L1
related:
  - '[[2026-02-22-mcp-testing-adr]]'
  - '[[2026-07-17-mcp-testing-research]]'
---

# `mcp-testing` plan

- [x] `S01` - Ground the sweep: inventory both repos' MCP tests and amend the testing decision with the functional assertion floor; `.vault/adr/2026-02-22-mcp-testing-adr.md`.
- [x] `S02` - Add a raw JSON-RPC serving probe and wire it into the leaked-pipe and parent-pid watchdog e2es so lifecycle asserts count only from a serving server; `tests/unit/mcp_server/test_watchdog.py`.
- [x] `S03` - Upgrade the entrypoint tests: handshake through the stdout-purity queue, EOF exit proven from a serving session, zero-input EOF kept as the documented exception; `tests/mcp/test_mcp_entrypoint.py`.
- [x] `S04` - Hand the rag half to that repo's board with the inventory and the floor spec; `repo workflow`.
- [ ] `S05` - Run gates, dispatch code review, resolve findings, append audit entries, open stacked PR; `quality gates`.

## Description

Execute the functional assertion floor amendment of
2026-02-22-mcp-testing-adr, grounded by the two-repo inventory in
2026-07-17-mcp-testing-research: every test that spawns the real MCP
server must prove served capability (handshake identity, exact tool
surface, or a measurable payload) before lifecycle assertions count.
Core's four offenders are upgraded on a branch stacked on the
watchdog-parity PR; the rag half is handed to that repo's board.

## Steps

## Parallelization

Sequential: the inventory and decision precede the test upgrades, and the
gates close over the finished set. S02 and S03 are independent of each
other.

## Verification

- Both watchdog e2es assert a completed handshake and the exact nine-tool
  surface through their own transport pipes before any kill or exit
  assertion.
- The entrypoint suite proves serving through the stdout-purity queue and
  EOF exit from a serving session; the zero-input EOF exception is
  documented in the test itself.
- The amended decision names the floor and its one degenerate exception;
  the rag board carries the sibling half with the reference probe.
- Gates green (unit gate, MCP suites, tests tree, ty both platforms,
  dependency audit); review dispatched and findings resolved; stacked PR
  open and ready.
