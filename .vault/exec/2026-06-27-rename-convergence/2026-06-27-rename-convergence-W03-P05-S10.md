---
tags:
  - '#exec'
  - '#rename-convergence'
date: '2026-06-27'
modified: '2026-06-27'
step_id: 'S10'
related:
  - "[[2026-06-27-rename-convergence-plan]]"
---

# Migrate the vault.rename envelope incoming_rewritten to per-link counting and update its test

## Scope

- `src/vaultspec_core/tests/cli/test_vault_rename.py`

## Description

- Strengthen the incoming-rewrite assertion from a per-document lower bound to the exact per-link count of one, with a comment recording the contract change.
- Add a dedup case where a referrer lists the rename target ahead of the old stem, proving the per-link count is zero on a drop even though one document is modified, the legitimate per-link versus per-document divergence.
- Add a directory-at-destination case proving a refused rename never rewrites incoming links, so no dangling link is left behind.
- Add a mid-apply rollback case that drives the exact transaction-plus-cascade composition the verb uses, raises a real exception after the rename and link rewrite land, and asserts byte-for-byte restoration with no dangling link.

## Outcome

- The `vault rename` suite pins the per-link `incoming_rewritten` contract and proves the dangling-link window is closed both on a refused rename and on a rolled-back mid-apply failure.
- All assertions read real bytes on a real filesystem; no test doubles are used and no existing assertion was weakened.

## Notes

- A true mid-apply failure cannot be induced through the public verb single-threaded because the collision pre-check guards the destination and the post-rename steps swallow filesystem errors, so the rollback test drives the same engine and cascade the verb composes and raises a real exception inside the transaction.
