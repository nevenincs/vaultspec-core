---
tags:
  - '#exec'
  - '#install-mode'
date: '2026-07-13'
modified: '2026-07-13'
related:
  - "[[2026-07-13-install-mode-plan]]"
---

# `install-mode` `P03` summary

Phase P03 made the builtin MCP definition and the four canonical pre-commit hook entries
mode-parameterized, so a workspace renders the `uvx` launch form in tool mode and the
existing `uv run` form in dependency mode. All six Steps (S12-S17) closed; review found
and fixed a doctor drift-detection gap.

- Modified: `src/vaultspec_core/builtins/mcps/vaultspec-core.builtin.json`
- Modified: `src/vaultspec_core/core/mcps.py`
- Modified: `src/vaultspec_core/core/workspace_mode.py`
- Modified: `src/vaultspec_core/core/commands.py`
- Modified: `src/vaultspec_core/core/diagnosis/collectors.py`
- Modified: `src/vaultspec_core/tests/cli/test_mcp_provider_files.py`
- Modified: `src/vaultspec_core/tests/cli/workspace_factory.py`
- Modified: `src/vaultspec_core/tests/cli/test_flow_bugs.py`

## Description

The builtin MCP definition (S12) was made mode-neutral: its `command` and `args` fields
carry sentinel placeholder tokens (`@@VAULTSPEC_INSTALL_MODE_COMMAND@@` and
`@@VAULTSPEC_INSTALL_MODE_ARGS@@`) that cannot collide with real content, mirrored
byte-for-byte into the repository's own seeded copy so the `BuiltinVersionSignal` drift
hash sees no change.

`render_mcp_definition_for_mode` and `resolve_render_mode` (S13) landed in
`core/mcps.py` and `core/workspace_mode.py`: token-guarded substitution maps dependency
mode to the unchanged `uv run python -m vaultspec_core.mcp_server.app` launch and tool
mode to `uvx --from vaultspec-core python -m vaultspec_core.mcp_server.app`.
`collect_mcp_servers` gained an optional `mode` input, and `mcp_sync` / `mcp_status`
resolve the render mode from an explicit argument or the committed declaration,
defaulting to dependency mode when no declaration exists (the Q6 legacy-workspace
bridge).

The hook-entry renderers (S14) turned `CANONICAL_ENTRY_PREFIX`, the `_HOOK_DEFS` values,
`CANONICAL_PRECOMMIT_HOOKS`, and `CANONICAL_HOOK_ENTRIES` into functions of
`InstallMode` via `entry_prefix_for_mode`, `hook_defs_for_mode`,
`canonical_precommit_hooks_for_mode`, and `canonical_hook_entries_for_mode`, while the
pre-existing module-level constants stayed pinned to dependency mode for byte-identical
behavior at that point in the plan. `_scaffold_precommit` (S15) was then updated to read
the resolved mode and render through these functions, and `collect_precommit_state` was
pulled forward to derive its expected entries from the resolved mode rather than the
hardcoded dependency-mode constant, so a default tool-mode install is not misdiagnosed
as non-canonical.

WorkspaceFactory-based tests pinned both renderers end to end against real installs: S16
asserts the whole MCP command-and-args map for both modes plus the Q6 legacy-bridge
fallback after removing the declaration; S17 asserts all four hook entries
byte-precisely for both modes plus the same bridge behavior, marked `unit` so it runs
under the CI gate despite living in an otherwise `integration`-marked module.

## Review revisions

Commit `8e72b6ec` (`install-mode P03 review`) fixed a CRITICAL doctor drift-detection
gap: the doctor's MCP registry drift check was rendering the comparison against the
wrong mode, which would have flagged a correctly provisioned workspace as drifted. The
fix routes the check through the resolved mode so the registry renders for comparison
consistently with the workspace's actual declaration. Commit `91be09d1` rebuilt the
install-mode feature index after the P03 exec records landed.

## Verification

A probe confirmed both renders byte-precise and custom MCP definitions passed through
untouched. `ruff check` and `ty check` were clean; the mode-rendering test classes added
in S16 and S17 passed alongside the pre-existing provider-file and flow-bug suites.
