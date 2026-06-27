---
tags:
  - '#exec'
  - '#rename-convergence'
date: '2026-06-27'
modified: '2026-06-27'
step_id: 'S14'
related:
  - "[[2026-06-27-rename-convergence-plan]]"
---

# Wire check_feature_rename_integrity into run_all_checks and the checks package exports

## Scope

- `src/vaultspec_core/vaultcore/checks/__init__.py`

## Description

- Import `check_feature_rename_integrity` in the checks package and add it to `__all__` in alphabetical position.
- Append the check after `check_features` in both the read-only and the fix branches of `run_all_checks`, calling it with no `feature` or `fix` arguments since it is read-only, the same way `check_encoding` is appended.
- Update the `run_all_checks` docstring check inventory to name the new check.

## Outcome

- `vault check all` runs the new check in position immediately after `features` in both modes.
- The fix branch appends the check directly without a graph refresh, mirroring the read-only `check_encoding`.

## Notes

- The check-order stability test was updated separately to include the new check at its wired position.
