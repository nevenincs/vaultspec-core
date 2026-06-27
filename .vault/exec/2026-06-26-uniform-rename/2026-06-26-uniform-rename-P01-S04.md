---
tags:
  - '#exec'
  - '#uniform-rename'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S04'
related:
  - "[[2026-06-26-uniform-rename-plan]]"
---

# Run the structure case-rename suite to confirm no behavior change

## Scope

- `src/vaultspec_core/vaultcore/checks/tests/test_structure_case_rename.py`

## Description

- Run the structure case-rename suite as the regression gate for the extraction.
- Run the wider checks test directory and the second importer suite that pulls the rewrite engine and budget constant from the structure check.
- Run the full unit gate.
- Lint and type-check both touched modules.
- Verify both module import orders are free of an import cycle in a fresh interpreter.

## Outcome

The structure case-rename suite passed. The combined regression-gate run across the case-rename suite and the second importer suite passed at forty tests. The full unit gate passed at one thousand three hundred seventy-seven selected tests with zero failures. The linter and the type checker both reported all checks passed on the shared module and the structure check. Importing the shared module first and importing the checks package first both succeeded, and the re-exported symbols are identity-equal to the shared-module originals.

## Notes

No behavior change was observed; the existing suite was the proof. No test was modified, skipped, or weakened.
