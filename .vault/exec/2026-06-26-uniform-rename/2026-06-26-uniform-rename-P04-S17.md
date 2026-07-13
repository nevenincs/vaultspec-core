---
tags:
  - '#exec'
  - '#uniform-rename'
date: '2026-06-26'
modified: '2026-06-27'
step_id: 'S17'
related:
  - "[[2026-06-26-uniform-rename-plan]]"
---

# Test cross-feature incoming wiki-link rewrite in other features documents

## Scope

- `src/vaultspec_core/vaultcore/tests/test_rename_feature.py`

## Description

- Added `TestCrossFeatureLinks` with a second feature's adr whose `related:` block points at a document of the renamed feature.
- Assert the incoming wiki-link is rewritten to the new stem while the neighbour's own feature tag is left untouched, and that the result's `cross_links` reports the neighbour document as the link source.

## Outcome

Two tests pass. Incoming links that archive could only warn about are actually rewritten, and the rewrite is reported.

## Notes

The neighbour lives in a different feature, so this exercises the whole-vault `related:` cascade rather than the intra-feature path.
