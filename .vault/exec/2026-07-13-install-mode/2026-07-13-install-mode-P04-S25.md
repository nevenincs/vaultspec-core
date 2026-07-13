---
tags:
  - '#exec'
  - '#install-mode'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S25'
related:
  - "[[2026-07-13-install-mode-plan]]"
---

# Add WorkspaceFactory-based tests asserting the floor-constraint refusal fires when the running package version is below minimum_vaultspec_version and passes when at or above it

## Scope

- `src/vaultspec_core/tests/cli/test_migration_triggers.py`

## Description

- Add `_running_version` and `_bind_context` helpers, the latter binding the workspace context the floor check reads through `get_context().target_dir`.
- Add a `TestFloorConstraint` class that installs a real workspace, writes a floored declaration, binds the context, then diagnoses and resolves through the real `resolve()` path.
- Assert a floor of 999.999.999 (above the running version) refuses with a `VaultSpecError` naming both the floor and the running version.
- Assert a floor equal to the running version and a floor of 0.0.1 (below it) both resolve without raising, returning a `ResolutionPlan`.

## Outcome

The refuse-and-tell floor is verified at all three thresholds through the real resolver invocation surface rather than a direct call to the helper: the tests provision a workspace, commit a declaration floor, bind the workspace context, and drive `diagnose` then `resolve`, so the refusal fires exactly where a real `sync` would hit it. The below-floor case asserts the message carries the actionable pair the remediation needs (the floor and the running version); the at-floor and above-floor cases confirm no false refusal. Three tests pass.

## Notes

The tests derive the running version from `importlib.metadata` and set the floor relative to it (equal, below, and an unreachable 999.999.999 above), so the expected outcomes come from the floor semantics in the specification, not from copied output. Context binding is required because `_resolve_version_warning` reads the active workspace context rather than the `target` argument passed to `resolve()`. No mocks, patches, or stubs; the workspace, declaration, and manifest are all real on disk.
