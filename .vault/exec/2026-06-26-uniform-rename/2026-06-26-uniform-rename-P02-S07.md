---
tags:
  - '#exec'
  - '#uniform-rename'
date: '2026-06-26'
modified: '2026-06-27'
step_id: 'S07'
related:
  - "[[2026-06-26-uniform-rename-plan]]"
---

# Implement the old-to-new tag-block rewriter with flow-to-block normalization

## Scope

- `src/vaultspec_core/vaultcore/query.py`

## Description

- Add a tag-block rewriter that scans only the frontmatter tags block and swaps the single source-feature tag for the target, leaving the directory tag and every other line untouched.
- Detect and strip a leading byte-order mark, detect the line-ending convention, and restore both on write so the rewrite is byte-faithful.
- Normalize a flow-style inline tags value to block form first by parsing it through the YAML loader, swapping the feature entry during the rebuild, and refusing rather than emitting unparseable bytes.
- Preserve the exact dash indentation and surrounding quote style of the rewritten block entry.

## Outcome

- The rewriter returns the new content and a changed flag, touching only the tags block and never body prose. Carriage-return line endings on a tested document survive the swap intact.

## Notes

- The block-scan and quote-preserving approach borrows the patterns proven in the index directory-tag insertion and the related-link normalizer, so no new parsing strategy was introduced.
