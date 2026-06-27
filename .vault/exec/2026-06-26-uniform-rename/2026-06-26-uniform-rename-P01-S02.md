---
tags:
  - '#exec'
  - '#uniform-rename'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S02'
related:
  - "[[2026-06-26-uniform-rename-plan]]"
---

# Move the related-link rewrite engine and its regexes into the shared module

## Scope

- `src/vaultspec_core/vaultcore/rename_ops.py`

## Description

- Move the related-link rewrite engine `_rewrite_incoming_refs` into the shared module, exposing it as the public `rewrite_incoming_refs`.
- Move its module-level regex `_RELATED_ENTRY_RE` and the `_FRONTMATTER_LINE_BUDGET` constant alongside it.
- Re-point the engine's lazy `get_config` import to the shallower relative depth and keep `atomic_write` as a top-level import.
- Import the diagnostic types the engine writes into lazily inside the function rather than at module top.

## Outcome

The whole-tree wiki-link cascade now lives beside the path renamer. Every preserved behavior carried over unchanged: the rename-chain collapse, cycle detection and drop, duplicate-target dedup, exact-then-lowercase stem matching, anchor and alias preservation, CRLF line-ending preservation, UTF-8 BOM round-trip, the closing-fence guard, and the frontmatter line budget. The structure check still drives the engine after its filename fixes through a private re-export alias.

## Notes

The BOM sentinel uses the six-character source escape rather than a literal zero-width glyph, matching the original and keeping the source legible. The diagnostic types are imported lazily inside the function to avoid a module-level dependency on the checks package, which would otherwise form an import cycle through the structure check.
