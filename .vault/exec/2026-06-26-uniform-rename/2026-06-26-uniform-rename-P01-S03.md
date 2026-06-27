---
tags:
  - '#exec'
  - '#uniform-rename'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S03'
related:
  - "[[2026-06-26-uniform-rename-plan]]"
---

# Re-point the structure check to import the rename primitives from the shared module

## Scope

- `src/vaultspec_core/vaultcore/checks/structure.py`

## Description

- Remove the four path-rename functions and the related-link rewrite engine, its regex, and its budget constant from the structure check.
- Import the two primitives back from the shared module under their original private names so internal call sites stay unchanged.
- Re-export the frontmatter budget constant under a redundant alias so external importers keep resolving it from the structure check.
- Drop the now-unused `uuid4` and `atomic_write` imports.

## Outcome

The structure check holds no duplicate copy of either primitive; it has exactly one implementation, imported from the shared module. The private aliases `_rename_document_path` and `_rewrite_incoming_refs` remain module-level names of the structure check and are the same function objects as the shared-module originals, so `_fix_filename` and `check_structure` behave identically. Both regression-gate test files that import these symbols directly from the structure check stay green without edits.

## Notes

The alias re-exports follow the project's one-per-line `as` import house style to satisfy the linter's combine-as-imports setting. No test files were touched.
