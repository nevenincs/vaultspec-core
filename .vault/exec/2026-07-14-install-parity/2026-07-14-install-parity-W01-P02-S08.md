---
tags:
  - '#exec'
  - '#install-parity'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S08'
related:
  - "[[2026-07-14-install-parity-plan]]"
---

# Generalize dependency detection to report both project-dependency and default-dev-group evidence for a named distribution, keeping a core-scoped wrapper for the existing call sites

## Scope

- `src/vaultspec_core/core/workspace_mode.py`

## Description

- Add a three-valued `DependencyEvidence` StrEnum (`RUNTIME`, `DEV`, `NONE`) documenting the leak-boundary taxonomy the ADR draws.
- Replace the boolean `_pyproject_declares_vaultspec_dependency` probe with `detect_package_evidence(pyproject, package)`, package-aware and placement-aware for any named distribution.
- Classify `[project.dependencies]` and `[project.optional-dependencies]` as `RUNTIME`; classify only the default `dev` group (`[dependency-groups].dev` and legacy `[tool.uv.dev-dependencies]`) as `DEV`; classify named non-default groups and absence as `NONE`.
- Keep PEP 503 canonicalization and the lenient posture (a malformed or unreadable manifest reads as `NONE`, never raising).
- Reimplement `_pyproject_declares_vaultspec_dependency` as a thin backward-compatible boolean shim over the new detector so the existing `resolve_install_mode` call site stays green until `S09` retires it.

## Outcome

Detection now reports a distribution's placement as one of runtime-leaking, dev-scoped, or none, keyed on the PEP 621 / PEP 735 leak boundary rather than bare presence. Runtime outranks dev when a package appears in both, so a leaking placement is never masked by a dev declaration. `optional-dependencies` is deliberately classified as runtime evidence because those requirements are written into built distribution metadata and install with their extra, so they leak downstream exactly as project dependencies do. Named non-default groups are left unclassified because they stay inert until enabled with `--group` and would require persisting a group name, which the ADR places out of scope. The compat shim preserves the pre-change presence-or-absence answer, so no behavior changes in this Step; the mapping from evidence to the DEV mode lands in `S09`. Scoped `ruff` and `ty` clean; the 35 existing `test_workspace_mode.py` unit tests pass unchanged.

## Notes

The dev-group detection test at `test_vaultspec_in_dependency_group_is_dependency_evidence` still asserts the old DEPENDENCY outcome; it stays green here because the compat shim collapses evidence to a boolean and `resolve_install_mode` is untouched. That test is corrected to expect DEV in `S12`, alongside the resolver mapping change in `S09`, so the behavior shift and its test update land together rather than in this pure-refactor Step.
