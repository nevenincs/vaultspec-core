---
tags:
  - '#exec'
  - '#mcp-stdio-lifetime'
date: '2026-07-16'
modified: '2026-07-16'
body_hash: 'sha256:1ddad70c02dec1d96541f57f11e53fcb9351c0b057d813d91cb6478f5f72eafb'
step_id: 'S03'
related:
  - "[[2026-07-16-mcp-stdio-lifetime-plan]]"
---

# Wire arm_client_watchdog into \_serve immediately before mcp.run with stderr debug logging of armed or skipped outcome

## Scope

- `src/vaultspec_core/mcp_server/app.py`

## Description

- Call `arm_client_watchdog` in `_serve` immediately before `mcp.run()`
- Log the armed or not-armed outcome at debug level to stderr

## Outcome

`src/vaultspec_core/mcp_server/app.py` committed as `3fe9db32`; EOF-only
behavior preserved whenever arming declines.

## Notes

None.
