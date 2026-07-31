---
tags:
  - '#exec'
  - '#mcp-stdio-lifetime'
date: '2026-07-17'
modified: '2026-07-17'
body_hash: 'sha256:3b6ac84c79b6bec6a76f0b41c5a31fc7cef69c22d774af921730bab4c1884163'
step_id: 'S10'
related:
  - "[[2026-07-17-mcp-stdio-lifetime-plan]]"
---

# Document the watchdog contract and knobs in the MCP doc and register VAULTSPEC_STDIO_WATCHDOG in the CLI reference env table via the builtins source

## Scope

- `docs/MCP.md`

## Description

- Add a Server lifetime section to the MCP doc: contract, anchors, event line, both knobs
- Register `VAULTSPEC_STDIO_WATCHDOG` in the CLI reference env table (builtins source), roll the mirror via install --upgrade and sync

## Outcome

Committed as `4a7480ea`.

## Notes

The env table is a hand-zone; only the command inventory is generator-owned.
