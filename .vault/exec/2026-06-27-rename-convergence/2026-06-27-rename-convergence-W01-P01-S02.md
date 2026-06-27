---
tags:
  - '#exec'
  - '#rename-convergence'
date: '2026-06-27'
modified: '2026-06-27'
step_id: 'S02'
related:
  - "[[2026-06-27-rename-convergence-plan]]"
---

# Implement RenameTransaction: caller-supplied snapshot, containment-checked case-safe rename, record-write/create/dir, context-manager rollback, and domain-lock acquisition

## Scope

- `src/vaultspec_core/vaultcore/rename_engine.py`

## Description

- Add the `RenameTransaction` context manager constructed from a managed root and an optional lock target, holding the reverse journal whose field semantics mirror the former journal dataclass exactly.
- Acquire the domain advisory lock on enter through an exit stack when a lock target is supplied, honoring the lock helper's skip-when-parent-absent behavior without creating the parent directory.
- Implement the caller-supplied snapshot that captures original bytes per file, skipping symlinks and non-files and logging unreadable files, with the caller deciding the set rather than the engine rglobbing a root.
- Implement the containment-checked, case-safe rename that guards both endpoints against the managed root, delegates to the shared rename primitive, and journals the pair only on success.
- Add the record helpers for created files, created directories, and removed directories.
- Implement the context-manager rollback that, on a propagating exception, walks the journal in the exact original order (delete created files, recreate removed dirs, reverse renames LIFO, drop created dirs, restore snapshots) under the lock, then releases the lock and never suppresses the exception.

## Outcome

- The engine is a drop-in transaction surface: a caller snapshots its own set, funnels renames and create/remove records through the transaction, and inherits byte-for-byte rollback identical to the hardened backend.
- A clean exit releases the lock and rolls nothing back; an exception rolls back under the lock and re-raises.

## Notes

- The rollback ordering and the symlink-aware snapshot/restore logic are line-for-line equivalent to the original helpers, so the transaction is behavior-preserving by construction; the only added mechanic is the per-domain lock acquisition, which is a no-op when the lock parent directory is absent.
