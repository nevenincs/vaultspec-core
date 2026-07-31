---
tags:
  - '#exec'
  - '#vault-scale-performance'
date: '2026-07-27'
modified: '2026-07-27'
body_schema: 'body-v1'
body_hash: 'sha256:da7626be01f6019a5c9305f3259ec53d37df5017f6b2b76316e5101208bcc017'
step_id: 'S19'
related:
  - "[[2026-07-27-vault-scale-performance-plan]]"
---

# add the synthetic-corpus complexity scale gate asserting operation counts and cross-size scaling ratios under a dedicated marker

## Scope

- `src/vaultspec_core/tests/scale/test_scale_gate.py`

## Description

- Add the benchmark-marked scale gate asserting exactly one corpus
  read per document, memoized plan parsing, and at-most-linear
  tag-extraction growth across a four-fold corpus step.

## Outcome

All three gate tests pass; budgets are operation counts and scaling
ratios observed by a real profiler, never wall-clock.

## Notes

Gate corpora are generated at test time by the canonical synthetic
generator and never committed.
