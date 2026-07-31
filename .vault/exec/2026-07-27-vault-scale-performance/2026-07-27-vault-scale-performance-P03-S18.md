---
tags:
  - '#exec'
  - '#vault-scale-performance'
date: '2026-07-27'
modified: '2026-07-27'
body_schema: 'body-v1'
body_hash: 'sha256:bf1c7f203c1a457a34fa12710552248fa215c8148416705dc6192f2698a7ceb4'
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
