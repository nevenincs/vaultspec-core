---
tags:
  - '#exec'
  - '#envelope-optimization'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:daaf74c8f1941759a1038ab8ef35f385d2ed530852758253ffcf36ccfb03726e'
step_id: 'S13'
related:
  - "[[2026-08-23-envelope-optimization-plan]]"
---

# Bound and validate the find limit and split the two-mode result row

## Scope

- `src/vaultspec_core/mcp_server/tools/documents.py`

## Description

- Bound and validate the row limit.
- Prune optional null fields from structured content.

## Outcome

The limit was an unbounded integer reaching a Python slice, so a negative value silently returned 659 of 660 rows - 158,957 bytes - and a large one returned everything. Both are now refused rather than clamped: for a tool call an out-of-range limit is a caller error, and failing loudly beats returning nearly everything.

The result row is a sixteen-field superset covering two modes, so twelve fields were null on every feature row and eight on every document row. Pruning them took the unfiltered listing from 4,802 bytes to 1,282.

## Notes

Blanket null-exclusion was wrong and broke the plan tools: a field can be required and nullable, and dropping one produced a payload that failed its own output-schema validation on the way back out. Required fields keep their nulls; only fields the schema already treats as omissible are pruned.
