---
tags:
  - '#exec'
  - '#provider-mcp-enrollment'
date: '2026-07-15'
modified: '2026-07-15'
step_id: 'S02'
related:
  - "[[2026-07-15-provider-mcp-enrollment-plan]]"
---

# Implement ownership state and provider-scope target resolution

## Scope

- `src/vaultspec_core/core/mcps.py`

## Description

- Resolve enrolled MCP-capable providers to verified native project, local, and user targets.
- Reject Codex local and unsupported Antigravity broader-scope combinations.
- Honor `CODEX_HOME` for explicit Codex user scope.
- Add strict external ownership sidecar parsing and writing contracts.
- Separate declaring package identity from the optional tool-mode distribution spec and strip all mode metadata before host output.

## Outcome

Production resolver checks selected Claude JSON and Codex TOML paths correctly, rejected Codex local, rendered RAG tool mode through `vaultspec-rag[mcp]`, and preserved dependency/dev `uv run`. Ruff and type checks pass. The existing MCP suite reached 52 passes; one current test expects dependency mode from an unspecified fresh install even though Core now defaults to tool mode.

## Notes

The stale fresh-install mode assertion is preserved for the dedicated test-update step rather than changing product behavior or weakening the test during this architecture step.
