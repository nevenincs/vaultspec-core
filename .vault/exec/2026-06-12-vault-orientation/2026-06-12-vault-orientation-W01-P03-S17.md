---
tags:
  - '#exec'
  - '#vault-orientation'
date: '2026-06-12'
modified: '2026-06-13'
body_hash: 'sha256:7c8601925084856e0494e917f53dc6c029881aa7db954bad1ea7edf7f8b3c553'
step_id: S17
related:
  - '[[2026-06-12-vault-orientation-plan]]'
---

# refresh the target document's modified stamp on related-frontmatter link mutations

## Scope

- `src/vaultspec_core/vaultcore/related_surgery.py`

## Description

- Import the shared `refresh_modified_stamp` helper and `datetime` into `src/vaultspec_core/vaultcore/related_surgery.py`.
- In both `remove_related_entries` and `append_related_entry`, refresh the modified stamp on the assembled `new_content` immediately before the atomic write, applied to the `source_newline`-joined text so the document's line-ending convention is preserved.

## Outcome

`vault link add` and `vault link remove` now refresh the target document's modified stamp to today, since both operations rewrite the target's `related:` frontmatter. The two functions are the single shared implementation behind `link add`, `link remove`, and the dangling-link fixer, so all related-frontmatter surgery now restamps consistently with no drift. When `append_related_entry` synthesises a brand-new frontmatter block (a document that had none), that block carries no `date:` anchor and the helper leaves it unchanged, which is the correct degrade. Targeted suites pass; ruff and ty clean.

## Notes

The refresh runs only on the code paths that actually reach a write: `remove_related_entries` returns early with no write when nothing matched, and `append_related_entry` returns early on an idempotent no-op, so a no-change call never restamps.
