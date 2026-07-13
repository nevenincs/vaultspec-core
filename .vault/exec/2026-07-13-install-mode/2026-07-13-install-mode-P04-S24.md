---
tags:
  - '#exec'
  - '#install-mode'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S24'
related:
  - "[[2026-07-13-install-mode-plan]]"
---

# Add WorkspaceFactory-based tests asserting the resolver emits a mode-mismatch fix-hint step with the correct remediation target and that collect_precommit_state reports COMPLETE for a correctly-provisioned tool-mode workspace

## Scope

- `src/vaultspec_core/tests/cli/test_collectors.py`

## Description

- Add a `TestModeMismatchResolution` class with a `_clean_diagnosis` helper whose only non-clean axis is the mode-mismatch signal, so the assertions isolate the mode advisory from unrelated resolver warnings.
- Assert a `MISMATCH` diagnosis makes `resolve()` emit exactly one workspace.json warning naming both `install --upgrade` and `install --mode`.
- Assert `CLEAN` and `UNKNOWN` emit no mode advisory.
- Assert `collect_precommit_state` reports `COMPLETE` for a real tool-mode install, confirming the P03 pull-forward derives expected entries from the persisted tool mode rather than the dependency-mode shape.

## Outcome

The resolver's mode-mismatch advisory is verified to fire only on `MISMATCH` and to carry both remediation targets, while `CLEAN` and the legacy `UNKNOWN` state stay silent. The tool-mode precommit assertion closes the loop opened in P03: a correctly-provisioned tool-mode workspace, whose hook entries are the uvx form, diagnoses `COMPLETE` because the collector derives its expected entries from the persisted mode, so tool mode is no longer diagnosed as non-canonical against the dependency shape. Four tests pass.

## Notes

The resolver tests build the diagnosis directly rather than binding a workspace context, so `_resolve_version_warning` short-circuits on the absent context and the floor constraint does not interfere; the assertions filter warnings by the `workspace.json` substring so any unrelated advisory cannot mask or inflate the result. The precommit assertion runs against a real WorkspaceFactory install through `_install_and_init`, which binds the workspace context the collector reads. No mocks, patches, or stubs.
