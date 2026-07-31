---
tags:
  - '#exec'
  - '#vault-scale-performance'
date: '2026-07-27'
modified: '2026-07-27'
body_schema: 'body-v1'
body_hash: 'sha256:beafc2adf13509aa831cbb4cc238aa993344fea7e5bf8435432d4517b126dbfc'
related:
  - "[[2026-07-27-vault-scale-performance-plan]]"
---

# `vault-scale-performance` `P03` summary

All three Steps closed. The report phase is bounded and the complexity
budgets are gated: human check output caps at fifty findings per check and
the graph tree at a thousand lines, both with marked truncation and the
uncapped JSON surface as the machine contract; console geometry is queried
once per run; and a benchmark-marked scale gate asserts the read budget,
plan-parse memoization, and linear scaling as operation counts over
generated synthetic corpora.

- Modified: `src/vaultspec_core/vaultcore/checks/_base.py`
- Modified: `src/vaultspec_core/graph/api.py`
- Modified: `src/vaultspec_core/console.py`
- Created: `src/vaultspec_core/tests/scale/__init__.py`
- Created: `src/vaultspec_core/tests/scale/test_scale_gate.py`

## Description

The render caps extend the established output contract's marked-truncation
clause to the check and graph report surfaces; corpora below the caps
render byte-identically. The console pins its width at construction when a
real terminal answers, eliminating the per-line terminal-size queries.
The scale gate runs the whole non-mutating check pass under a real
profiler at two corpus sizes and fails on any second read of a document,
any unmemoized plan re-parse, or superlinear tag-extraction growth - the
deterministic form of the complexity budgets, immune to CI timing noise.
