---
tags:
  - '#exec'
  - '#uniform-rename'
date: '2026-06-26'
modified: '2026-06-27'
step_id: 'S18'
related:
  - "[[2026-06-26-uniform-rename-plan]]"
---

# Test reverse-journal rollback restores original state after an induced mid-apply failure

## Scope

- `src/vaultspec_core/vaultcore/tests/test_rename_feature.py`

## Description

- Added `TestRollback`. Induced a real mid-apply failure with no mocks by reading the deterministic apply order from the dry-run plan and planting a real directory at the second computed destination filename, so the OS rename of that document fails only after the first rename has already landed.
- Snapshot every `.md` byte before the call, assert `rename_feature` raises `VaultSpecError`, then assert every file is byte-identical to the pre-call snapshot and that no document is added or missing.

## Outcome

One test passes. The reverse journal undoes the already-applied rename and restores the vault byte-for-byte.

## Notes

A directory at a destination passes collision detection (`is_file()` is false) but fails the filesystem rename, which is the realistic mid-apply fault this step needed.
