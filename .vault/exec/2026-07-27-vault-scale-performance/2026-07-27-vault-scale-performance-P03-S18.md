---
tags:
  - '#exec'
  - '#vault-scale-performance'
date: '2026-07-27'
modified: '2026-07-27'
body_schema: 'body-v1'
step_id: 'S18'
related:
  - "[[2026-07-27-vault-scale-performance-plan]]"
---

# cap the unscoped vault graph tree render with marked truncation

## Scope

- `src/vaultspec_core/graph/api.py`

## Description

- Cap the graph tree render at a thousand lines with a marked
  truncation line pointing at feature scoping and the JSON surface.

## Outcome

The unscoped tree render is bounded; the title keeps the full
corpus counts.

## Notes

None.
