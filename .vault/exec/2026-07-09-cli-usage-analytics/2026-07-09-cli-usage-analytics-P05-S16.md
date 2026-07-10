---
tags:
  - '#exec'
  - '#cli-usage-analytics'
date: '2026-07-09'
modified: '2026-07-09'
step_id: 'S16'
related:
  - "[[2026-07-09-cli-usage-analytics-plan]]"
---

# Implement the command-and-flag n-gram metric as a pure function over the canonical flag and token sequence

## Scope

- `statistic/metrics/ngrams.py`
- `tests/statistic/test_metrics.py`

## Description

- Add the command-and-flag n-gram metric as a pure function over the record stream.
- Count each verb-path-plus-sorted-flag-names shape as a repeated invocation pattern.
- Count every unordered flag-name pair as a co-occurrence, values never entering keys.
- Rank both aggregates by descending count with a total tie-break on the key.
- Assert exact pattern counts and sorted co-occurrence pairs with synthetic records.

## Outcome

The n-gram metric surfaces repeated invocation shapes and co-occurring flags without
leaking any flag value, feature tag, or path into the keys. Two synthetic tests pass
and the module is lint and type clean.

## Notes

Only canonical flag names enter the pattern and co-occurrence keys, so the metric
output is safe to render into the aggregate-only report.
