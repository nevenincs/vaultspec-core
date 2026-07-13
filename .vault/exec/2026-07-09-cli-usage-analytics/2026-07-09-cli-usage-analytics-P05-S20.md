---
tags:
  - '#exec'
  - '#cli-usage-analytics'
date: '2026-07-09'
modified: '2026-07-10'
step_id: 'S20'
related:
  - "[[2026-07-09-cli-usage-analytics-plan]]"
---

# Implement the overuse-and-dead-surface metric as a pure function comparing observed counts against the declared-capability denominator

## Scope

- `statistic/metrics/surface.py`
- `tests/statistic/test_metrics.py`

## Description

- Add the overuse-and-dead-surface metric as a pure function over records and inventory.
- Count observed verb paths and split them into declared usage and undeclared usage.
- Compute dead surface as the inventory verb-path set minus the observed set.
- Report the declared-surface coverage fraction alongside the raw denominators.
- Sort every partition for a total, deterministic ordering.
- Assert the exact overuse, undeclared, and dead-surface partitions with synthetic records.

## Outcome

The surface metric places observed usage next to the declared denominator: the overuse
view ranks disproportionately-hit verbs and the dead surface is the closed set of
declared verbs never invoked. One synthetic test passes and the module is lint and
type clean.

## Notes

The dead surface is an exact set difference against the inventory, so it is verifiable
rather than an estimate.
