---
tags:
  - '#exec'
  - '#cli-usage-analytics'
date: '2026-07-09'
modified: '2026-07-10'
step_id: 'S21'
related:
  - "[[2026-07-09-cli-usage-analytics-plan]]"
---

# Implement the token-and-turn-cost-per-class metric as a pure function grouping cost by verb class

## Scope

- `statistic/metrics/cost.py`
- `tests/statistic/test_metrics.py`

## Description

- Add the token-and-turn-cost-per-class metric as a pure function over the record stream.
- Group attributed token cost by the leading verb naming the command class.
- Report attributed-call and total-call counts so an unattributed verb is not read cheap.
- Keep per-source totals separate to mark Claude and Codex cost as directional.
- Rank verb classes by descending cost for a deterministic ordering.
- Assert per-verb grouping and per-source separation with synthetic records.

## Outcome

The cost metric groups attributed token cost by command class and keeps Claude and
Codex totals apart, since one side is a per-message approximation and the other a
snapshot-delta. Two synthetic tests pass and the module is lint and type clean.

## Notes

Records without an attributed cost still contribute to the call count, so a low total
is distinguishable from a genuinely cheap verb.
