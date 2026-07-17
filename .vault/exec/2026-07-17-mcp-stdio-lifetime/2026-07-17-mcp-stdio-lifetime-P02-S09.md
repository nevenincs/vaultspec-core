---
tags:
  - '#exec'
  - '#mcp-stdio-lifetime'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S09'
related:
  - "[[2026-07-17-mcp-stdio-lifetime-plan]]"
---

# Add POSIX-contract assertions for the reparent poll and explicit-pid path exercised on the current platform honestly

## Scope

- `tests/unit/mcp_server/test_watchdog.py`

## Description

- Platform-branch the new tests so POSIX asserts the reparent-poll contract honestly (armed=True, poll cadence bounds)
- Keep the real-server parent-pid e2e platform-neutral (explicit-pid poll covers POSIX)

## Outcome

Committed as `e6737158`.

## Notes

POSIX branches execute only on a non-Windows checkout; CI does not run this tree.
