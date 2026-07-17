---
tags:
  - '#exec'
  - '#mcp-stdio-lifetime'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S02'
related:
  - "[[2026-07-17-mcp-stdio-lifetime-plan]]"
---

# Add VAULTSPEC_STDIO_WATCHDOG kill switch honored before any arming, with off values matching the sibling repo

## Scope

- `src/vaultspec_core/mcp_server/watchdog.py`

## Description

- Add `STDIO_WATCHDOG_ENV` and `watchdog_disabled()` honoring `0`/`false`/`off`/`no`
- Check the switch before any anchor work in `arm_client_watchdog`

## Outcome

Kill switch active on every platform path; committed as `7659724d`.

## Notes

None.
