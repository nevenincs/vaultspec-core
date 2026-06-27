---
tags:
  - '#exec'
  - '#rename-convergence'
date: '2026-06-27'
modified: '2026-06-27'
step_id: 'S09'
related:
  - "[[2026-06-27-rename-convergence-plan]]"
---

# Route \_execute_rename through the engine and switch its incoming-link rewrite to the shared rewrite_incoming_refs

## Scope

- `src/vaultspec_core/cli/edit_cmd.py`

## Description

- Route the document rename in `_execute_rename` through the shared `RenameTransaction` bound to the docs root, acquiring the docs-domain advisory lock via `docs_lock_target` for the transaction lifetime.
- Snapshot the renamed document plus every incoming-reference document (still discovered through the vault graph) before any mutation, so the reverse journal can restore them byte-for-byte.
- Reverse the prior ordering: rename the file first via `tx.rename`, then run the shared `rewrite_incoming_refs` cascade, closing the window where links were rewritten before the file moved.
- Retire the duplicate link rewriter `_rewrite_incoming_related` and replace its stamp side effect with a new `_refresh_doc_stamps` helper plus a `_cascade_paths` helper that refresh the renamed doc and every relinked doc.
- Migrate the `incoming_rewritten` envelope value to the cascade's per-link `fixed_count`; preserve every other envelope key, the blob-hash optimistic-concurrency guard, and the dry-run path.

## Outcome

- `vault rename` now drives the same transactional engine, lock, and link cascade as the feature rename, gaining byte-for-byte rollback and case-safe rename, with the dangling-link window eliminated.
- `_rewrite_incoming_related` is removed; `_find_incoming_refs` is retained because it still supplies the snapshot set. The `_add_related_link` and `remove_related_entries` helpers keep their other callers and are no longer imported here.
- `ruff format`, `ruff check`, and `ty check` pass on the changed module.

## Notes

- The originating step row claimed the cascade refreshes relinked docs; it does not. To honour vault-orientation decision D3 and avoid a silent regression, `_refresh_doc_stamps` refreshes the renamed doc and every cascade-touched doc, mirroring the feature-rename backend. No envelope key changed beyond `incoming_rewritten`.
