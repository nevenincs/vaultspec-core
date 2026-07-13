---
tags:
  - '#exec'
  - '#install-mode'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S27'
related:
  - "[[2026-07-13-install-mode-plan]]"
---

# Add WorkspaceFactory-based tests for the install --upgrade migration inference covering a legacy dependency-mode workspace, a legacy tool-shaped workspace, and idempotency on a second upgrade run

## Scope

- `src/vaultspec_core/tests/cli/test_migration_triggers.py`

## Description

- Add `TestUpgradeModeInference`, three WorkspaceFactory tests that provision a
  real mode-shaped workspace, strip the committed declaration to reproduce a
  pre-install-mode legacy state, and drive `install --upgrade` through the Q6
  inference path.
- Cover a legacy dependency-mode workspace (uv-run hooks, uv-run MCP, pyproject
  listing vaultspec-core): assert the upgrade infers and records dependency
  mode and leaves the coherent workspace diagnosing clean.
- Cover a legacy tool-shaped workspace (uv-run hooks but no pyproject and no MCP
  config): assert the upgrade infers tool mode and, in the same run, renders the
  hooks and the re-added MCP command in the uvx shape, with mode-mismatch clean.
- Cover idempotency: assert a second upgrade rewrites the declaration to
  byte-identical content and preserves the persisted dependency mode.
- Assert against the on-disk declaration, `_observed_precommit_mode`,
  `_observed_mcp_mode`, and `collect_mode_mismatch_state`; no mocks or stubs.

## Outcome

Three tests pin the S26 behaviour. The tool-shaped case is the ordering pin the
P03 review demanded: it fails if the declaration is written after the sync and
scaffold renderers, because the hooks would then render uv-run against a
tool-mode declaration. The full migration-triggers module stays green (20
passed) and ruff is clean on the file.

## Notes

The tool-shaped test removes the pre-existing `.mcp.json` before upgrading. A
managed MCP entry that diverges from the target mode's shape is governed by the
separate force-gate sync policy (a managed-but-different entry is skipped under a
non-force upgrade), so removing it isolates the render-mode path the S26 ordering
fix actually governs, letting the freshly-added entry reflect the inferred mode.
The hook scaffold, by contrast, rewrites its canonical entries unconditionally,
so the hook-shape assertion pins the ordering fix directly. That MCP force-gate
asymmetry on a mode-flip migration is carried into the S33 conformance review.
