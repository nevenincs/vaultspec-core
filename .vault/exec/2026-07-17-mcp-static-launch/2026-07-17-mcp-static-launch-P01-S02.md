---
tags:
  - '#exec'
  - '#mcp-static-launch'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S02'
related:
  - "[[2026-07-17-mcp-static-launch-plan]]"
---

# Sweep orphaned MCP server processes holding venv DLLs and repair the venv with an explicit uv sync

## Scope

- `environment recovery`

## Description

- Enumerate processes launched from this worktree's venv; the two
  lock-holding search-mcp processes had already exited, so no kill was
  needed.
- Repair the environment with an explicit uv sync (resolved 128, checked 107
  packages; reinstalled the editable vaultspec-core the interrupted
  connect-time sync had removed).
- Verify recovery: single pywin32-312 dist-info remains, the CLI resolves at
  0.1.46, and the stdio MCP server answers a real initialize request.

## Outcome

Venv restored to a coherent state; core MCP server handshakes over stdio;
recovery used only explicit dev actions, matching the static-execution
contract the feature enforces.

## Notes

The pywin32-311 dist-info residue reported during diagnosis was cleaned by
the sync; no manual site-packages surgery was required.
