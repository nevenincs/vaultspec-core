---
tags:
  - '#exec'
  - '#install-parity'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S09'
related:
  - "[[2026-07-14-install-parity-plan]]"
---

# Add a package parameter to resolve_install_mode and insert DEV into the Q5 precedence chain ahead of the TOOL default when dev-group evidence is found

## Scope

- `src/vaultspec_core/core/workspace_mode.py`

## Description

- Add a `package` parameter to `resolve_install_mode` defaulting to `vaultspec-core`, threaded so a companion distribution resolves its own entry and its own detection evidence through the same precedence chain.
- Switch the persisted-declaration read from the `read_workspace_declaration` facade to the per-package `read_package_declaration`, preserving the top-of-function fail-fast validation on a corrupt declaration.
- Map detection evidence to modes: runtime-leaking placement resolves to `DEPENDENCY`, default-dev-group placement resolves to the non-leaking `DEV`, and no placement leaves the tool-mode default.
- Extend the impossible-combo refusal to cover `DEV` as well as `DEPENDENCY` when no `pyproject.toml` exists, with a mode-named message; keep the explicit-differs-from-evidence case permitted.
- Retire the now-unused `_pyproject_declares_vaultspec_dependency` boolean shim introduced in `S08`.
- Correct the one directly-invalidated detection test to assert the new `DEV` outcome for a default-dev-group placement.

## Outcome

`resolve_install_mode` is now package-parameterized and three-mode aware while keeping the `install-mode` Q5 precedence order (explicit, persisted, detected, default) unchanged. The DEV member enters the chain only through detection and only ahead of the tool-mode default: a distribution found solely in the default dev group resolves to DEV, so a workspace that scopes the harness to its dev group reads as the honest non-leaking placement rather than a full runtime dependency. The refusal now guards both placement modes symmetrically, since neither a runtime dependency nor a dev-group dependency is expressible without a project manifest to declare it in; an explicit mode that merely runs ahead of the manifest still passes, since the contributor may be about to add the placement. Scoped `ruff` and `ty` clean; 143 install/upgrade/mode/detection unit tests pass, and the broader sync and collector callers of the changed signature stay green.

## Notes

Per the one-commit-per-step contract, the single existing detection test whose expected outcome this behavior change inverts (`[dependency-groups].dev` placement, previously asserted DEPENDENCY) is corrected here so the commit stays green rather than landing red and being repaired one Step later. The comprehensive new taxonomy and DEV-precedence coverage still lands in `S12` as the plan sequences; this Step touches only the one test the change directly falsifies.

### Review refinement (LOW)

P02 code review noted the impossible-combo refusal hint hardcoded "declares vaultspec-core as a dependency" even when the refused mode was dev. The follow-up commit parameterizes the hint per refused mode via `_refusal_hint_for_mode`: dependency points at a runtime dependency, dev points at the default dev dependency group. The refusal message and its typed-error contract are otherwise unchanged.
