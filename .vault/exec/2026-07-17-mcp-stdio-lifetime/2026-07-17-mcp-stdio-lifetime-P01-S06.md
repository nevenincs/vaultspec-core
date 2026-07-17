---
tags:
  - '#exec'
  - '#mcp-stdio-lifetime'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S06'
related:
  - "[[2026-07-17-mcp-stdio-lifetime-plan]]"
---

# Add --parent-pid entrypoint option watched ahead of discovery and wire arming outcomes through \_serve logging

## Scope

- `src/vaultspec_core/mcp_server/app.py`

## Description

- Add `--parent-pid` option to the vaultspec-mcp typer callback
- Thread it through `_serve` into `arm_client_watchdog(parent_pid=...)`, watched ahead of discovery and never grace-pruned

## Outcome

Flag proves out end-to-end against the real server module; committed as `7659724d`.

## Notes

None.
