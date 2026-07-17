---
tags:
  - '#exec'
  - '#mcp-stdio-lifetime'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S07'
related:
  - "[[2026-07-17-mcp-stdio-lifetime-plan]]"
---

# Add kill-switch and parent-pid override tests driving real worker subprocesses

## Scope

- `tests/unit/mcp_server/test_watchdog.py`

## Description

- Add in-process kill-switch test with real environment mutation restored in finally
- Add worker-subprocess kill-switch test (armed=False, stays alive)
- Extend the dead-client test to the parent_pid override and assert the structured exit event JSON

## Outcome

Committed as `e6737158`.

## Notes

None.
