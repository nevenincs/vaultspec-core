---
tags:
  - '#exec'
  - '#install-mode'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S23'
related:
  - "[[2026-07-13-install-mode-plan]]"
---

# Add WorkspaceFactory-based tests for collect_mode_mismatch_state detecting uv run hook entries and a non-uvx MCP command in a tool-mode workspace, and the reverse mismatch in a dependency-mode workspace

## Scope

- `src/vaultspec_core/tests/cli/test_collectors.py`

## Description

- Add a `TestModeMismatchState` class exercising `collect_mode_mismatch_state` against real WorkspaceFactory installs.
- Cover the legacy case: a workspace with no committed declaration reads `UNKNOWN`.
- Cover a tool-declared workspace with dependency-shaped artifacts: install dependency mode (real `uv run` hook entries and non-uvx MCP command), assert `CLEAN` first, then rewrite the declaration to tool mode and assert `MISMATCH`.
- Cover the reverse: install tool mode (real uvx artifacts), assert `CLEAN`, then rewrite the declaration to dependency mode and assert `MISMATCH`.

## Outcome

The mode-mismatch collector is verified in both directions against artifacts produced by the real provisioning path, not hand-typed fixtures: the observed side of each comparison comes from parsing a genuine `.pre-commit-config.yaml` and `.mcp.json` written by a real install of the opposite mode. Each direction also asserts the coherent pre-flip state reads `CLEAN`, so the `MISMATCH` result is attributable to the declaration flip rather than a pre-existing drift. Three tests pass.

## Notes

The mismatch is staged by installing in the mode that produces the desired artifact shape, then writing the committed declaration to the other mode through `write_workspace_declaration` - the same public writer the CLI uses. This keeps the artifacts real (no synthesized YAML or JSON) while making the declaration name a mode the artifacts were not provisioned for, which is exactly the drift the collector must catch. No mocks, patches, or stubs; assertions run against the real on-disk workspace.
