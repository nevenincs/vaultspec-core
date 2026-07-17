---
tags:
  - '#exec'
  - '#mcp-static-launch'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S06'
related:
  - "[[2026-07-17-mcp-static-launch-plan]]"
---

# Update every launch-shape assertion and add legacy-shape and no-sync render tests across the renderer, per-package sync, collector, and mode-flip suites

## Scope

- `src/vaultspec_core/tests/cli`

## Description

- Update the four hardcoded dependency-mode launch assertions in
  `test_collectors.py` (`TestRenderLaunchForMode`, `TestRenderMcpDefinitionForMode`,
  and the end-to-end `TestInstallModeDevEndToEnd` test) to the `--no-sync`
  shape.
- Update the `_DEPENDENCY_LAUNCH` constant in `test_mcp_provider_files.py`,
  asserted whole against a real `install` run.
- Confirm `test_mcp_per_package_sync.py` and `test_install_mode_flip.py`
  already derive their expected shapes through `render_launch_for_mode` and
  `_MODE_MCP_LAUNCH`, so they move automatically and need no edits.
- Add `TestObservedMcpMode` to `test_collectors.py`, importing the private
  `_observed_mcp_mode` matcher directly, covering: the current
  `--no-sync`-guarded shape maps to `DEPENDENCY`; the legacy bare `uv run`
  shape maps to `DEPENDENCY`; the `uvx` shape maps to `TOOL`; and an
  arbitrary un-guarded shape that is neither candidate returns `None`, so the
  legacy recognition cannot loosen into accepting arbitrary shapes.
- Confirm the existing `test_mixed_partial_shapes_is_mismatch` test, which
  writes the legacy bare shape as a mismatch fixture, still passes now that
  the legacy shape resolves to `DEPENDENCY` (it still mismatches a
  tool-declared workspace).
- Run ruff check/format and ty on the changed test files.

## Outcome

Every launch-shape assertion across the renderer, per-package sync,
provider-file, collector, and mode-flip suites now agrees with the
`--no-sync` shape. `TestObservedMcpMode` directly exercises the legacy-shape
recognition added in `S05` and proves it stays bounded. 120 tests pass across
`test_mcp_per_package_sync.py`, `test_collectors.py`, `test_mcp_provider_files.py`,
and `test_install_mode_flip.py`; ruff check, ruff format, and ty all pass on
the changed files.

## Notes

None.
