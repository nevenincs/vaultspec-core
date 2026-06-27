---
tags:
  - '#exec'
  - '#rename-convergence'
date: '2026-06-27'
modified: '2026-06-27'
step_id: 'S11'
related:
  - "[[2026-06-27-rename-convergence-plan]]"
---

# Acquire the docs-domain lock in the structure-rename cascade fix path

## Scope

- `src/vaultspec_core/vaultcore/checks/structure.py`

## Description

- Wrap the entire mutating cascade in `check_structure` under the docs-domain advisory lock keyed on `docs_lock_target`, so it serializes against the feature rename and the document rename on one sentinel.
- Acquire the lock around both the per-document fix loop, where `_fix_filename` performs the file renames, and the follow-up `rewrite_incoming_refs` pass, not the ref-rewrite alone, since the renames are the dangerous mutations.
- Gate the lock on the fix run with a conditional context manager, so read-only passes take no lock and behave identically.
- Honour the skip-if-parent-absent contract of the advisory lock and never create the data directory, keeping the lock a no-op in un-provisioned trees.

## Outcome

- The structure-rename cascade now serializes against the other docs-domain mutators on the shared sentinel, while read-only structure checks are unchanged.
- The structure case-rename regression suite stays green and the lock engages only when files are actually renamed.

## Notes

- The originating step row suggested wrapping the ref-rewrite section; wrapping only that would leave the `_fix_filename` renames outside the lock and able to interleave with a concurrent feature rename, so the lock was widened to cover the whole fix-path cascade.
