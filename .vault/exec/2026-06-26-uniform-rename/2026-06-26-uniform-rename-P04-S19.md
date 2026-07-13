---
tags:
  - '#exec'
  - '#uniform-rename'
date: '2026-06-26'
modified: '2026-06-27'
step_id: 'S19'
related:
  - "[[2026-06-26-uniform-rename-plan]]"
---

# Test force-merge into an existing feature and refusal on per-file path collision

## Scope

- `src/vaultspec_core/vaultcore/tests/test_rename_feature.py`

## Description

- Added `TestForceMergeAndCollision`. The force-merge case renames a source feature into an existing target with `--force` and asserts both documents end under `#new`, the migrated document carries the new filename and tag, and the source feature empties.
- The collision case gives both features an adr of the same date and type so the post-swap filename already exists; it asserts the rename is refused with a clear `VaultSpecError` and the vault is byte-identical.

## Outcome

Two tests pass. Force merges consolidate features; a per-file path collision fails safely before any mutation.

## Notes

The merged feature also gains a regenerated index document, which the assertion accounts for via a subset check rather than an exact type list.
