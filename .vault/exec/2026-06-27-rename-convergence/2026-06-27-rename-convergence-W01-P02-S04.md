---
tags:
  - '#exec'
  - '#rename-convergence'
date: '2026-06-27'
modified: '2026-06-27'
step_id: 'S04'
related:
  - "[[2026-06-27-rename-convergence-plan]]"
---

# Run the rename_feature and structure case-rename suites to confirm byte-identical behavior

## Scope

- `src/vaultspec_core/vaultcore/tests/test_rename_feature.py`

## Description

- Run the feature-rename, security, and encoding suites plus the feature-rename CLI suite to confirm the engine extraction is byte-identical.
- Run the structure case-rename suite and the flow-bugs suite to confirm the shared primitives are unaffected.
- Run the formatter, linter, and type checker on the changed engine and query modules.
- Run the full unit gate and compare the passed count against the established baseline.

## Outcome

- The four rename-focused suites pass with no behavior change; the structure case-rename and flow-bugs suites pass.
- Formatter, linter, and type checker report no findings on the changed files; an initially flagged unused import and an over-long docstring line were fixed at the source.
- The full unit gate passes at the established baseline count with zero deltas, confirming the wave adds no tests and changes no behavior.

## Notes

- No regression test changed behavior, so no test was edited to fit the engine; the engine was made to match the existing suites, as required.
