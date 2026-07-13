---
tags:
  - '#exec'
  - '#install-mode'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S08'
related:
  - "[[2026-07-13-install-mode-plan]]"
---

# Wire resolve_install_mode into install_run so the mode is resolved once at provision time, persisted to workspace.json, and an explicit --mode request that conflicts with detection raises a loud VaultSpecError refusal

## Scope

- `src/vaultspec_core/core/commands.py`

## Description

- Replace the trivial explicit-or-default resolution in `install_run` with a
  call to `resolve_install_mode`, so the mode is resolved once at provision time
  through the full Q5 precedence chain.
- Inherit the loud, typed refusal for the impossible combination (`--mode dependency` with no `pyproject.toml`) from `resolve_install_mode`, which now
  raises before any scaffolding.
- Keep persistence unchanged: the resolved mode still flows through
  `_persist_resolved_mode` into both the committed declaration and the manifest
  echo in the fresh-install and upgrade paths.

## Outcome

`install --mode` now honors the ADR Q5 precedence: explicit over persisted over
detection over default tool. A standalone probe confirmed the hard refusal fires
with a remediation hint for `--mode dependency` in a repo with no
`pyproject.toml`; dependency detection from a `pyproject.toml` that lists
vaultspec-core persists dependency mode both with and without the explicit flag.
The install, workspace-mode, and flow-bug suites pass (61 tests); ruff and ty
are clean.

## Notes

The resolution moved to just after the skip-core guard, ahead of the dry-run
branches, so an impossible `--mode dependency --dry-run` also refuses rather than
previewing an unbuildable workspace. `resolve_install_mode` is imported locally
inside `install_run` to keep the module's import graph flat, matching the
surrounding late-import convention.
