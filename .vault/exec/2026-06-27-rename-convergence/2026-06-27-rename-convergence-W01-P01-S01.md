---
tags:
  - '#exec'
  - '#rename-convergence'
date: '2026-06-27'
modified: '2026-06-27'
step_id: 'S01'
related:
  - "[[2026-06-27-rename-convergence-plan]]"
---

# Create the shared rename-engine module with root-generalized \_assert_within and the symlink-safe restore helper

## Scope

- `src/vaultspec_core/vaultcore/rename_engine.py`

## Description

- Create the new shared `vaultcore` rename-engine module to hold the reusable transaction mechanics extracted from the hardened feature-rename backend.
- Add the root-generalized containment guard, copied verbatim from the docs-scoped guard with only the parameter name changed from a docs-specific directory to a generic managed root; the resolve-and-parent-chain body and the raised error are unchanged.
- Move the symlink-safe byte-restore helper verbatim from the query module so a restore unlinks a symlinked target before writing fresh bytes at the in-bounds path.

## Outcome

- The module exposes the generalized `_assert_within(managed_root, path)` and `_safe_restore_bytes(path, original)` for the transaction and for the docs-scoped wrapper that callers and tests still import.
- Behavior is identical to the original docs-scoped guard: the containment unit tests in the security suite pass unchanged against the wrapper that now delegates to the generalized form.

## Notes

- The error message text is retained verbatim ("outside the vault document tree") to keep the security suite byte-identical green; generalizing the wording for the resource domain is deferred to the later waves that adopt the engine there.
