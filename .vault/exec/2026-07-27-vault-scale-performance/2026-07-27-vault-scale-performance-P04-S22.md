---
tags:
  - '#exec'
  - '#vault-scale-performance'
date: '2026-07-27'
modified: '2026-07-27'
body_schema: 'body-v1'
body_hash: 'sha256:6a7a6274fc39428774df3831de83db38c692cc82393a0c4fff4d0b8654796037'
step_id: 'S22'
related:
  - "[[2026-07-27-vault-scale-performance-plan]]"
---

# add the engine parity test asserting rustworkx and networkx betweenness agree on the synthetic corpus

## Scope

- `src/vaultspec_core/graph/tests/test_analysis_engine.py`

## Description

- Add the engine parity suite: both real engines run on the same
  built graphs (full and feature-scoped) and must agree to 1e-12,
  plus a guard that the wheel is actually present in this
  environment and a flow test through the metrics surface.

## Outcome

All 4 parity tests pass; the full graph suite (147 tests including
the envelope contract tests) passes against rustworkx-computed
scores.

## Notes

None.
