---
tags:
  - '#exec'
  - '#rename-convergence'
date: '2026-06-27'
modified: '2026-06-27'
step_id: 'S16'
related:
  - "[[2026-06-27-rename-convergence-plan]]"
---

# Add real-filesystem tests for each drift class plus a clean-vault pass

## Scope

- `src/vaultspec_core/vaultcore/checks/tests/test_feature_rename_integrity.py`

## Description

- Add a real-filesystem test module with no test doubles, marked as a unit suite.
- Cover the positive drift case: an exec record whose feature tag disagrees with its folder feature is an ERROR that names the folder, cites an example record, and carries both the observed folder feature and the conflicting tag plus a `vault feature rename` hint.
- Cover one error per folder, separate drifted folders each reported, and a mixed folder where a matching record does not mask a conflicting one.
- Cover the skips: uncategorized and untagged records, `_archive` and `.obsidian` subtrees, non-UTF-8 records, and folders lacking the dated-feature shape.
- Cover suite integration: `run_all_checks` includes the check in both branches and surfaces the drift.
- Add negative guards: a narrative-named authored doc whose filename differs from its tag is not flagged, a narrative-named record whose tag matches its folder is not flagged, and a missing index is not flagged.

## Outcome

- 17 tests pass. Every assertion guards the optional diagnostic path so the whole-codebase type-check hook stays clean.

## Notes

- The negative tests are the regression guard against silently reintroducing the authored filename-segment-vs-tag false positive that the implementation deliberately avoids.
