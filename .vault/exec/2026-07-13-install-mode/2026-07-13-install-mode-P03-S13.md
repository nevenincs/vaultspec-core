---
tags:
  - '#exec'
  - '#install-mode'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S13'
related:
  - "[[2026-07-13-install-mode-plan]]"
---

# Add a render_mcp_definition_for_mode function that substitutes the placeholder command and args with the uv run python -m form in dependency mode and the uvx --from vaultspec-core python -m form in tool mode, and apply it in collect_mcp_servers before merge

## Scope

- `src/vaultspec_core/core/mcps.py`

## Description

- Add `render_mcp_definition_for_mode(definition, mode)`: token-guarded substitution of the mode-neutral command and args tokens into the concrete launch for the given mode; a definition carrying neither token passes through unchanged so custom servers are untouched.
- Add a mode-to-launch table pinning dependency mode to `uv run python -m vaultspec_core.mcp_server.app` (byte-identical to the pre-change rendered form) and tool mode to `uvx --from vaultspec-core python -m vaultspec_core.mcp_server.app`.
- Give `collect_mcp_servers` an optional `mode` input; when set, each parsed definition is rendered before return so the merge pipeline writes the mode-specific form, and when `None` the raw token definitions are returned for name-only callers.
- Resolve the render mode in `mcp_sync` and `mcp_status` from an explicit argument when given, else from the committed declaration via the new `resolve_render_mode`, whose legacy-absent rule renders dependency mode.
- Add `resolve_render_mode(target)` to `core/workspace_mode.py`: return the declared mode, or dependency mode when no declaration exists (the Q6 migration bridge for legacy workspaces).
- Thread the fresh-install resolved mode through `init_run` into its MCP sync, and persist the committed declaration before the post-scaffold provider sync so that sync pass renders the just-resolved mode rather than the dependency bridge.

## Outcome

The MCP definition renderer is live and mode-parameterized. A dependency-mode workspace renders the exact `uv` launch it always did, so existing installs see zero churn; a tool-mode workspace renders the `uvx --from vaultspec-core` launch. Fresh `install` writes the declaration before the provider sync re-renders, so a tool-mode workspace with no `pyproject.toml` produces a `uvx`-shaped `.mcp.json` that matches its own declaration and is not diagnosed as drifted. Standalone `sync` and `spec mcps status` on a workspace with no declaration render dependency mode, keeping legacy workspaces byte-identical until a mode is recorded. Verified with a probe that the two renders are byte-precise and that a custom definition passes through untouched, and by running a fresh synthetic install whose `.mcp.json` now carries the tool-mode launch.

## Notes

Two pre-existing sync tests asserted `.mcp.json` equals the seeded builtin verbatim; that contract changed deliberately (the seeded builtin is now mode-neutral tokens, the workspace file holds the rendered form), so both were updated to compare against the source rendered for the workspace's resolved mode rather than the raw seed. This required threading the resolved mode into `init_run` and persisting the declaration before the fresh-install provider sync; the `init_run` mode parameter is introduced here and its pre-commit-hook consumer is wired in the following step. The upgrade path continues to resolve the render mode from the existing declaration; an explicit mode conversion on `install --upgrade` against a legacy workspace is deferred to the migration phase per the plan.
