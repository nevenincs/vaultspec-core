---
tags:
  - '#exec'
  - '#firmware-mcp-primacy'
date: '2026-07-09'
modified: '2026-07-10'
step_id: 'S07'
related:
  - "[[2026-07-09-firmware-mcp-primacy-plan]]"
---

# Add the one-sentence Q3 subagent clause to the Agents section stating dispatched personas operate vaultspec through the CLI and MCP tools are not assumed inside subagents

## Scope

- `src/vaultspec_core/builtins/system/03-vaultspec.md`

## Description

- Add the one-sentence subagent clause to the Agents section of the system prompt.
- State that dispatched personas operate vaultspec through the CLI and that MCP tools are not assumed inside subagents.
- Place it immediately before the artifacts-and-approval closing paragraph.

## Outcome

- The system prompt now makes the per-surface split explicit: the orchestrating session may hold the tools, dispatched subagents reach vaultspec through the CLI only.

## Notes

- None.
