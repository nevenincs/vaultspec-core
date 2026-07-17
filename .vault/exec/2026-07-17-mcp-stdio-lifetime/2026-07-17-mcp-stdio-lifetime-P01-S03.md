---
tags:
  - '#exec'
  - '#mcp-stdio-lifetime'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S03'
related:
  - "[[2026-07-17-mcp-stdio-lifetime-plan]]"
---

# Emit one structured JSON exit event to stderr before every hard exit, shared by all anchors

## Scope

- `src/vaultspec_core/mcp_server/watchdog.py`

## Description

- Add `_exit_on_watched_death` flushing one JSON event line to stderr before `os._exit(0)`
- Route every anchor's exit through it

## Outcome

Event shape matches the sibling server's (`event`, `dead_ancestor_pid`, `dead_ancestor_exe`, `shim_pid`); committed as `7659724d`.

## Notes

None.
