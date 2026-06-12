---
tags:
  - '#exec'
  - '#graph-backend'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S32
related:
  - '[[2026-06-10-graph-backend-plan]]'
---

# add 500 and 5000 document scale benchmarks with generous thresholds

## Scope

- `src/vaultspec_core/graph/tests/test_scale.py`

## Description

- Added scale benchmarks that build real synthetic corpora at 500 and 5000 documents
  using the synthetic generator, parametrised over both sizes.
- Asserted the cold from-scratch build completes within a generous per-size ceiling and
  produces at least the requested number of real nodes.
- Asserted a primed warm cache load reproduces the cold build topology and is no slower
  than the cold parse it replaces.
- Marked the module with the dedicated benchmark marker so the default fast suite does
  not run it.

## Outcome

Both sizes pass: a cold 5000-document build completes in a few seconds, well under the
240-second ceiling, and the warm cache load is no slower than the cold parse. The
thresholds are deliberately loose so the tests catch a structural regression rather than
policing wall-clock seconds on a slow runner.

## Notes

The thresholds are regression tripwires, not service-level targets, per the phase brief:
the goal is to fail loudly on an accidental quadratic parse or a lost cache, not to
enforce a tight latency budget. The benchmark marker is registered in the sibling step
that edits the project manifest; until that lands, running these tests emits an
unknown-marker warning, which is benign. The corpus uses the default edge probability so
the graph is connected enough to exercise edge attribution and pagerank at scale.
