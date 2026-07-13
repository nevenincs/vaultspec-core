---
tags:
  - '#exec'
  - '#uniform-rename'
date: '2026-06-26'
modified: '2026-06-27'
step_id: 'S09'
related:
  - "[[2026-06-26-uniform-rename-plan]]"
---

# Implement reverse-journal apply with rollback, index regeneration, stamp refresh, and graph-cache invalidation

## Scope

- `src/vaultspec_core/vaultcore/query.py`

## Description

- Snapshot the original bytes of every non-archived markdown file under the docs directory, keyed by its pre-rename path, before any mutation.
- Apply in order: create destination exec folders, rename every authored document and exec record, remove the emptied old exec folders, rewrite each renamed document's feature tag block, delete the stale index, run the related-link cascade vault-wide, regenerate the new index from a freshly built uncached graph, then refresh the modified stamp on every renamed or relinked document.
- Record each applied rename, created directory, removed directory, and created file in a reverse journal as the apply proceeds.
- On any exception, walk the journal in reverse: delete created files, recreate removed folders, reverse the renames, drop created directories, and restore every snapshot's original bytes, then re-raise as a vault-spec error describing the rollback.

## Outcome

- The happy path renames every binding surface and leaves the post-rename vault passing the full check suite. Two induced mid-apply failures, one during the rename loop and one after the renames, tag rewrites, and link cascade had landed, each left the vault byte-identical to its pre-rename snapshot, with the cross-feature link content restored.

## Notes

- Graph-cache invalidation is intentionally left to the CLI layer in the next phase per the execution brief, so this backend imports nothing from the CLI. Index regeneration uses an uncached graph so it observes the just-renamed documents regardless of cache state. A separate dry-run path returns the computed plan and a predicted rewrite count while mutating nothing.
