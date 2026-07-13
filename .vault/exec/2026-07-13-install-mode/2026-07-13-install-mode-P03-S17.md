---
tags:
  - '#exec'
  - '#install-mode'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S17'
related:
  - "[[2026-07-13-install-mode-plan]]"
---

# Add WorkspaceFactory-based tests asserting all four canonical hook entries render the uv run --no-sync vaultspec-core prefix in dependency mode and the uvx --from vaultspec-core vaultspec-core prefix in tool mode

## Scope

- `src/vaultspec_core/tests/cli/test_flow_bugs.py`

## Description

- Add a hook-entry rendering test class that installs in each mode and reads the resulting local pre-commit hook entries from `.pre-commit-config.yaml`.
- Assert all four canonical hook entries equal the full expected command line (mode prefix plus the hook's subcommand) in dependency mode and in tool mode, comparing whole entries rather than substrings.
- Pin the Q6 migration bridge: after a tool-mode install, remove the committed declaration and re-sync, asserting the entries fall back to the dependency prefix.
- Mark the new class `unit` in addition to the module's `integration` mark so the unit gate exercises the mode-rendering guarantee.

## Outcome

All four canonical hook entries are pinned byte-precisely for both modes through a real install and a real sync against a temporary workspace, with no test doubles. A dependency-mode install produces `uv run --no-sync vaultspec-core ...` for every hook; a tool-mode install produces `uvx --from vaultspec-core vaultspec-core ...`. The bridge test proves that removing the declaration and re-syncing rewrites the hook entries back to the dependency prefix, so a pre-install-mode workspace is never silently converted to the tool form. The three new tests pass, and because they carry the `unit` mark they run under the phase's unit gate.

## Notes

The host module is `integration`-marked at module level; the new class adds an explicit `unit` mark so it is selected by the `-m unit` gate while remaining a real filesystem-driven integration test. The hook bridge re-sync does not need force: the scaffolder updates any hook entry that differs from the mode-resolved canonical entry regardless of force, unlike the MCP merge which skips a differing managed entry without force.
