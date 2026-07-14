---
tags:
  - '#exec'
  - '#install-parity'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S15'
related:
  - "[[2026-07-14-install-parity-plan]]"
---

# Apply the render_mode aliasing helper in render_mcp_definition_for_mode and key mcp_status and mcp_sync's default resolution to resolve_render_mode(target, package='vaultspec-core')

## Scope

- `src/vaultspec_core/core/mcps.py`

## Description

- Rewire `render_mcp_definition_for_mode` to produce its launch through the
  generalized `render_launch_for_mode`, which routes the mode through render_mode
  so the `DEV` member renders byte-identically to `DEPENDENCY` instead of falling
  off the two-key launch table (the end-to-end KeyError the P02 executor flagged).
- Read the target distribution and module from the definition's own
  substitution-metadata keys, defaulting to core's package and module, and strip
  those keys during substitution so they never reach the written `.mcp.json`.
- Key `mcp_status` and `mcp_sync`'s default mode resolution explicitly to
  `resolve_render_mode(target, package='vaultspec-core')`.

## Outcome

Rendering a `DEV`-mode definition now yields the dependency-shaped `uv run`
launch rather than raising; a companion-package definition carrying its own
package/module keys renders that package's launch through the same renderer; and
user-authored and already-rendered definitions still pass through untouched. The
MCP, sync, and mode-flip suites (77 tests) pass and `ty check` is clean.

## Notes

No incidents. The observed-shape matcher's own use of the launch table is
reworked in the S17 collector step.
