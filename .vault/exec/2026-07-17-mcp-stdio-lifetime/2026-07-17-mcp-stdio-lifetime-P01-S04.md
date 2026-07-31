---
tags:
  - '#exec'
  - '#mcp-stdio-lifetime'
date: '2026-07-17'
modified: '2026-07-17'
body_hash: 'sha256:8e82a27e03d47aec7090f03c7f21c0c65b6fcb84052d1f8f34a83b39f68ee824'
step_id: 'S04'
related:
  - "[[2026-07-17-mcp-stdio-lifetime-plan]]"
---

# Add PID-reuse-safe ancestor-chain fallback armed when stdin pipe resolution declines: startup handles, creation-time monotonicity, grace-window pruning, wait-any

## Scope

- `src/vaultspec_core/mcp_server/watchdog.py`

## Description

- Restructure the module to a platform-gated Win32 section with full argtypes for all eight bindings
- Port the PID-reuse-safe ancestor walk: toolhelp snapshot, creation-time monotonicity, startup handles
- Engage the fallback only when the client anchor is absent; grace-prune discovered targets only, wait-any over survivors

## Outcome

Fallback covers non-pipe launches previously left with no backstop; committed as `7659724d`.

## Notes

Grace window parameterized (`grace_seconds`) for real-process testability, matching the sibling installer's signature.
