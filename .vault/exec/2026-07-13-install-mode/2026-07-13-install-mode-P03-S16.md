---
tags:
  - '#exec'
  - '#install-mode'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S16'
related:
  - "[[2026-07-13-install-mode-plan]]"
---

# Add WorkspaceFactory-based tests asserting the MCP definition renders the uv run command form in dependency mode and the uvx --from form in tool mode after sync

## Scope

- `src/vaultspec_core/tests/cli/test_mcp_provider_files.py`
- `src/vaultspec_core/tests/cli/workspace_factory.py`

## Description

- Add a `mode` keyword to `WorkspaceFactory.install` that forwards an explicit provisioning mode to `install_run`, defaulting to `None` so existing callers are unaffected.
- Add a mode-rendering test class asserting a dependency-mode install renders the exact `uv run python -m ...` launch and a tool-mode install renders the exact `uvx --from vaultspec-core python -m ...` launch, comparing the whole command-and-args map rather than any substring.
- Assert the provider-native MCP config renders the same mode as the shared config.
- Pin the Q6 migration bridge: after a tool-mode install, remove the committed declaration and re-sync with force, asserting the render falls back to the dependency launch.

## Outcome

Both mode renderings are pinned end to end through a real install and sync against a temporary workspace, with no test doubles. The dependency and tool launches are asserted whole, so a regression in the command or any single argument fails the test. The provider-native `.agents/mcp_config.json` is asserted to carry the same mode-rendered launch as `.mcp.json`. The bridge test proves that a workspace with no declaration renders the dependency launch on sync, the guarantee that keeps a pre-install-mode workspace from silently flipping to the uvx form. All four new tests plus the five pre-existing provider-file tests pass.

## Notes

Dependency mode is only coherent when a `pyproject.toml` declares the dependency, so the dependency-mode test writes one before installing; without it an explicit `--mode dependency` install correctly refuses. The bridge re-sync uses force because a plain sync skips a managed entry that differs from its source, so only a forced sync rewrites the entry to the newly-resolved dependency launch. The `mode` keyword on the factory is shared test infrastructure reused by the hook-rendering tests in the next step.
