---
tags:
  - '#exec'
  - '#uniform-rename'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S14'
related:
  - "[[2026-06-26-uniform-rename-plan]]"
---

# Test dry-run returns the full plan and mutates nothing on disk

## Scope

- `src/vaultspec_core/vaultcore/tests/test_rename_feature.py`

## Description

- Added `TestDryRun` asserting the dry-run return value carries the full plan: `paths`, `exec_folders`, predicted `tag_rewrites` and `related_rewrites`, `link_renames`, `index`, `cross_links`, `collisions`, `dry_run` true, and a `status` of `unchanged`.
- Snapshot the bytes of every `.md` document before and after the dry-run and assert the document set and every file are byte-identical.

## Outcome

Two tests pass. The dry-run reports a complete plan and mutates no vault document.

## Notes

The auxiliary graph cache under `.vault/data/` is not a vault document and is excluded from the byte snapshot.
