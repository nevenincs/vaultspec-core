---
tags:
  - '#exec'
  - '#uniform-rename'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S20'
related:
  - "[[2026-06-26-uniform-rename-plan]]"
---

# Test flow-style tags normalization and feature index delete-and-regenerate

## Scope

- `src/vaultspec_core/vaultcore/tests/test_rename_feature.py`

## Description

- Added `TestFlowTagsAndIndex` with a research document whose frontmatter uses flow-style `tags: ['#old', '#research']`.
- Assert the tag is normalized to block form carrying `#new` (with `#old` gone), and that the old `{old}.index.md` is deleted while a fresh `{new}.index.md` is regenerated with `#index`/`#new` tags and a `related:` list pointing at the renamed documents.

## Outcome

Two tests pass. Flow-style tags are normalized on rewrite and the feature index is deleted and regenerated for the new name.

## Notes

A pre-flight sanity assertion confirms the flow-style document is discoverable by feature before the rename runs.
