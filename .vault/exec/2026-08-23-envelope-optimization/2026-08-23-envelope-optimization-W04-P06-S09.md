---
tags:
  - '#exec'
  - '#envelope-optimization'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:69230ce08f60fa3541c12164739f40af05131af977bcced76fb807ec84b39177'
step_id: 'S09'
related:
  - "[[2026-08-23-envelope-optimization-plan]]"
---

# Cap active features in the rollup, rank by recency and emit the total

## Scope

- `src/vaultspec_core/vaultcore/orientation_rollup.py`

## Description

- Cap the active-feature list in the rollup, ranked by latest activity.
- Carry the pre-cap total on the rollup so every consumer can report it.

## Outcome

The orientation call opens every session, so its cost is paid before an agent has done any work, and its largest field was a full dump of every active feature. Measured at 10,476 documents that field was 52% of a 259 kilobyte payload.

What was dropped was largely inert. Of the 660 features the uncapped payload carried, 68% had no plan at all, 42% had no activity in thirty days, and 30% were already complete.

## Notes

The row shape is unchanged - every field survives. The trade is real but narrow: ranking by recency means stalled features fall off first, so a caller surveying for stalled work must page rather than read one response. The total ships beside the list so that loss is visible rather than silent.
