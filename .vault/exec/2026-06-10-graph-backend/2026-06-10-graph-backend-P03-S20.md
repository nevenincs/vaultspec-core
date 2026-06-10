---
tags:
  - '#exec'
  - '#graph-backend'
date: '2026-06-10'
step_id: S20
related:
  - '[[2026-06-10-graph-backend-plan]]'
---

# extract the related-frontmatter line surgery from the dangling fixer into a shared CRLF-preserving atomic helper

## Scope

- `src/vaultspec_core/vaultcore/`

## Description

- Created `src/vaultspec_core/vaultcore/related_surgery.py` with `remove_related_entries` and `append_related_entry` as the canonical shared frontmatter surgery helpers.
- Both helpers preserve CRLF line endings, write atomically via bak+rename, and operate only on the `related:` frontmatter block.
- Refactored `src/vaultspec_core/vaultcore/checks/dangling.py` to delegate its `fix` path to `remove_related_entries` from the shared module; removed the now-redundant private `_remove_related_entries` implementation.
- Updated `src/vaultspec_core/vaultcore/checks/tests/test_dangling.py` to import `remove_related_entries` from the shared module (aliased as `_remove_related_entries` for test compatibility).
- All 4 existing dangling tests pass; ruff and ty checks clean.

## Outcome

Shared surgery helper lives at `src/vaultspec_core/vaultcore/related_surgery.py`. The dangling fixer and all future link verbs use one implementation.

## Notes
