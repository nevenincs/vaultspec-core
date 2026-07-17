---
tags:
  - '#exec'
  - '#mcp-static-launch'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S04'
related:
  - "[[2026-07-17-mcp-static-launch-plan]]"
---

# Add the no-sync guard to the dependency-mode branch of render_launch_for_mode and align its docstring with the static-execution contract

## Scope

- `src/vaultspec_core/core/mcps.py`

## Description

- Add `--no-sync` to the dependency-mode branch of `render_launch_for_mode`,
  changing the rendered launch to `uv run --no-sync python -m <module>`.
- Rewrite the function docstring's dependency-mode paragraph to state the
  static-execution contract: the launch resolves the existing venv and never
  installs, syncs, or otherwise mutates it, failing honestly instead of
  self-repairing at connect time.
- Rewrite the `_MODE_MCP_LAUNCH` module comment to drop the old
  "byte-identical to the launch every dependency-mode workspace has always
  synced" framing in favor of the same static-execution language.

## Outcome

`render_launch_for_mode` and the derived `_MODE_MCP_LAUNCH` convenience table
now render dependency-mode MCP launches with the `--no-sync` guard; tool-mode
bytes are unchanged. Ruff check and format both pass on the changed file.

## Notes

None.
