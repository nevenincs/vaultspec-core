---
tags:
  - '#exec'
  - '#mcp-testing'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S02'
related:
  - "[[2026-07-17-mcp-testing-plan]]"
---

# Add a raw JSON-RPC serving probe and wire it into the leaked-pipe and parent-pid watchdog e2es so lifecycle asserts count only from a serving server

## Scope

- `tests/unit/mcp_server/test_watchdog.py`

## Description

- Add a raw newline-JSON-RPC serving probe asserting initialize identity and the exact nine-tool surface
- Wire it into the parent-pid e2e over the server's own pipes
- Rework the leaked-pipe e2e's client script to handshake through the very pipe it later leaks, printing a SERVING verdict the test asserts before the kill

## Outcome

Both lifecycle e2es now count only from a proven-serving server; committed as `9caa4f48`. The blind boot sleeps became handshake round-trips, cutting the pair from ~40s to ~4s.

## Notes

None.
