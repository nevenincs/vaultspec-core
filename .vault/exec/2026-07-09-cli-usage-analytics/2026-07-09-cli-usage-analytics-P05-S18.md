---
tags:
  - '#exec'
  - '#cli-usage-analytics'
date: '2026-07-09'
modified: '2026-07-10'
body_hash: 'sha256:5f1f5168bfdb8255fa869970d4496c195c1edffeafc7fd07101a1a53d8a5865b'
step_id: 'S18'
related:
  - "[[2026-07-09-cli-usage-analytics-plan]]"
---

# Implement the feature-tag-usage metric as a pure function distributing --feature and -f values

## Scope

- `statistic/metrics/feature_tags.py`
- `tests/statistic/test_metrics.py`

## Description

- Add the feature-tag-usage metric as a pure function over the record stream.
- Read the canonical feature-tag field, which already folds the short flag form.
- Count the distribution of tag values and tally tagged versus untagged records.
- Rank the distribution by descending count with a tie-break on the tag value.
- Assert the exact distribution and the tagged/untagged split with synthetic records.

## Outcome

The feature-tag-usage metric reports how central feature scoping is to real usage:
the per-tag distribution plus the tagged and untagged totals. Tag values are project
slugs, not command bodies, so they are legitimate report content. One synthetic test
passes and the module is lint and type clean.

## Notes

The metric reads the single canonical tag field, so no short-form folding logic is
duplicated here.
