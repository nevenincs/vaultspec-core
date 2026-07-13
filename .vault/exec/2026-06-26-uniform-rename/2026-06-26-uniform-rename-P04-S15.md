---
tags:
  - '#exec'
  - '#uniform-rename'
date: '2026-06-26'
modified: '2026-06-27'
step_id: 'S15'
related:
  - "[[2026-06-26-uniform-rename-plan]]"
---

# Test happy-path rewrite of filenames, the feature tag, and related links

## Scope

- `src/vaultspec_core/vaultcore/tests/test_rename_feature.py`

## Description

- Added `TestHappyPath` over a feature with research, adr, plan, and an audit carrying a narrative topic infix (`...-perf-audit.md`).
- Assert every old filename is gone and each new one exists, the `#feature` tag in each document is rewritten to `#new`, intra-feature `related:` wiki-links are repointed to the new stems, and a body-prose mention of the old feature name survives verbatim.

## Outcome

Four tests pass. Filenames, the feature tag, and `related:` links all swap while free-form prose is untouched.

## Notes

The topic-infix audit confirms the anchored, date-keyed segment transform preserves an arbitrary narrative suffix.
