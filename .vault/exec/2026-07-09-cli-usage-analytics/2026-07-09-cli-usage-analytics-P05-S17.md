---
tags:
  - '#exec'
  - '#cli-usage-analytics'
date: '2026-07-09'
modified: '2026-07-10'
step_id: 'S17'
related:
  - "[[2026-07-09-cli-usage-analytics-plan]]"
---

# Implement the features-utilized metric as a pure function intersecting distinct (verb, subcommand) pairs with the capability inventory

## Scope

- `statistic/metrics/features.py`
- `tests/statistic/test_metrics.py`

## Description

- Add the features-utilized metric as a pure function over records and the inventory.
- Reduce the record stream to the distinct set of observed verb paths.
- Partition the observed set into declared-and-used versus observed-but-undeclared.
- Sort both partitions for a total, deterministic ordering.
- Assert the exact split against a hand-built capability inventory.

## Outcome

The features-utilized metric reports the exercised verb-path surface, splitting the
declared-and-used verbs from the undeclared candidate misses. It reports only verb
paths, never counts or command bodies. One synthetic test passes and the module is
lint and type clean.

## Notes

Undeclared verb paths are surfaced rather than dropped, consistent with the advisory
inventory contract.
