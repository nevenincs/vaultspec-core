---
tags:
  - '#exec'
  - '#cli-usage-analytics'
date: '2026-07-09'
modified: '2026-07-10'
step_id: 'S19'
related:
  - "[[2026-07-09-cli-usage-analytics-plan]]"
---

# Implement the tool-call-misses metric as a pure function sequencing records by retry_key to separate corrected retries and genuine misses from by-design non-zero exits

## Scope

- `statistic/metrics/misses.py`
- `tests/statistic/test_metrics.py`

## Description

- Add the tool-call-misses metric as a pure function over records and the inventory.
- Count only genuine error-status records so by-design findings never inflate the rate.
- Report advisory undeclared-flag candidates for flags absent from a declared verb.
- Sequence each session's records by activity timestamp for retry-correction detection.
- Emit a retry correction when an errored call is followed by a same-verb, differently
  flagged call, and ignore an identical reissue.
- Expose the miss rate as the genuine-error fraction of all records.

## Outcome

The misses metric separates genuine invocation errors from by-design non-zero exits,
so a findings status and the Claude venv noise stay out of the miss rate by
construction. It also surfaces advisory undeclared-flag candidates and the highest-
value retry-correction signal. Five synthetic tests pass and the module is lint and
type clean.

## Notes

The retry-correction pass groups by session and orders by timestamp; the record model
already carries the linkage anchor the adapters derive.
