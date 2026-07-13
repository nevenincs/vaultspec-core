---
tags:
  - '#exec'
  - '#cli-usage-analytics'
date: '2026-07-09'
modified: '2026-07-10'
step_id: 'S15'
related:
  - "[[2026-07-09-cli-usage-analytics-plan]]"
---

# Implement the verb-hotspots metric as a pure function counting each (verb, subcommand) leaf over the CallRecord stream

## Scope

- `statistic/metrics/hotspots.py`
- `tests/statistic/test_metrics.py`

## Description

- Add the verb-hotspots metric as a pure function over an iterable of call records.
- Count each full verb-path leaf with a Counter and rank by descending count.
- Break ties on the verb path itself so the ordering is total and deterministic.
- Return a tuple of frozen hotspot rows carrying the verb path and its count.
- Assert exact rankings and the empty-stream case with in-code synthetic records.

## Outcome

The hotspots metric ranks verb paths by invocation frequency with a deterministic
tie-break. It reads no clock and performs no I/O, so a fixed record set yields a
byte-identical ranking. Two synthetic tests pass and the module is lint and type
clean.

## Notes

The metric depends only on the frozen record model and the standard library, so it
carries no coupling to either source adapter.
