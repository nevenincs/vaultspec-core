---
tags:
  - '#exec'
  - '#rename-convergence'
date: '2026-06-27'
modified: '2026-06-27'
step_id: 'S03'
related:
  - "[[2026-06-27-rename-convergence-plan]]"
---

# Drive rename_feature through RenameTransaction, passing its non-archive snapshot set, with no behavior change

## Scope

- `src/vaultspec_core/vaultcore/query.py`

## Description

- Re-point the feature-rename apply path to open a transaction bound to the docs root with the docs-domain lock target, replacing the bespoke journal, the whole-tree snapshot helper, and the standalone rollback helper.
- Snapshot the same non-archive document set inside the transaction via a new docs-specific iterator that yields exactly the paths the former snapshot helper captured, leaving the per-file symlink and read-failure handling to the engine.
- Convert each apply step to record on the transaction: created exec folders, the containment-checked case-safe file renames through the transaction's rename, removed empty old exec folders, and the regenerated index's created file and directory.
- Keep the wrapped failure contract: any exception inside the transaction rolls the vault back byte-for-byte and is re-raised as the same "failed and was rolled back" error chained from the original cause.
- Preserve the docs-scoped containment guard as a thin wrapper that delegates to the engine's generalized guard, keeping the symbol importable for the callers and the security suite.
- Remove the now-dead private journal, snapshot, restore, and rollback helpers, and drop the unused rename-primitive import they pulled in.

## Outcome

- The feature-rename verb now drives the shared transaction with no observable change: the dry-run path, the return dict, every envelope field, and the rollback byte-identity are unchanged.
- The docs-scoped guard remains importable and behaves identically, so the security suite's direct import and assertions pass untouched.

## Notes

- The docs-domain lock target is passed straight to the lock helper; because no test vault has the data subdirectory, the lock is a no-op throughout this wave, matching the decision record's stated allowance and keeping behavior identical.
