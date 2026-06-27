---
tags:
  - '#exec'
  - '#rename-convergence'
date: '2026-06-27'
modified: '2026-06-27'
step_id: 'S07'
related:
  - "[[2026-06-27-rename-convergence-plan]]"
---

# Route hooks_rename through the engine on the resource domain

## Scope

- `src/vaultspec_core/core/hooks.py`

## Description

- Replace the bare `shutil.move` in `hooks_rename` with a `RenameTransaction` bound to the hooks directory and serialized on the same shared resource-domain lock sentinel as `resource_rename`.
- Resolve the hooks directory from the active context once, compute the destination filename with its preserved extension, and assert containment on both endpoints before the existence checks.
- Snapshot the hooks file and perform the move through the transaction so a failed rename rolls the file back byte-for-byte under the lock.
- Preserve the observable contract: the same new path is returned and the same `ResourceNotFoundError` / `ResourceExistsError` raises fire, now joined by a containment `VaultSpecError` that the CLI already catches.

## Outcome

- The fourth and last rename surface now drives the shared engine; the hook rename is containment-guarded, case-safe, lock-serialized, and rolls back on failure, with the `spec.hooks.rename` envelope unchanged.

## Notes

- A hook rename is a pure move with no content rewrite, so a single-step rename has nothing to partially undo; rollback is therefore exercised by an induced rename failure that leaves the source byte-identical rather than by undoing a completed multi-step mutation.
