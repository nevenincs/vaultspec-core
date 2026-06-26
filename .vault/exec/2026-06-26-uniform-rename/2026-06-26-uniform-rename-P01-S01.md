---
tags:
  - '#exec'
  - '#uniform-rename'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S01'
related:
  - "[[2026-06-26-uniform-rename-plan]]"
---

# Create the shared rename-primitives module and move the case-safe path renamer into it

## Scope

- `src/vaultspec_core/vaultcore/rename_ops.py`

## Description

- Create the new shared module `rename_ops.py` under `vaultcore`.
- Move the case-safe path renamer `_rename_document_path` verbatim, exposing it as the public `rename_document_path`.
- Move its three private helpers `_paths_refer_to_same_file`, `_case_rename_temp_path`, and `_absolute_path_text` alongside it.
- Adjust the relative-import depth for the new location (the module sits one level shallower than the structure check).
- Declare the module public API through `__all__`.

## Outcome

The case-safe rename hop, including the UUID temp-file two-hop for case-only renames on case-insensitive filesystems and the same-file destination guard, now lives in one module. Behavior is byte-for-byte identical to the original; the renamed public function is an exact move with only the def name changed. The structure check's `_fix_filename` continues to call the primitive unchanged via a private re-export alias added in S03.

## Notes

The module deliberately carries no module-level import from the checks package so that importing the shared module never triggers the checks import chain that points back at it. Both import orders were verified to be cycle-free in a fresh interpreter.
