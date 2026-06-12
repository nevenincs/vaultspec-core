---
tags:
  - '#exec'
  - '#graph-backend'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S17
related:
  - '[[2026-06-10-graph-backend-plan]]'
---

# add exact-value tests for every derived signal and the composed weight

## Scope

- `src/vaultspec_core/graph/tests/test_derived.py`

## Description

- Add a derived-edge test module with small on-disk vault fixtures, one per
  signal, asserting exact real values: reciprocity 1.0 in isolation,
  shared-feature 1.0, shared-tag counting a shared semantic tag, Jaccard 1.0
  for a single shared neighbour, Adamic-Adar exactly 1/ln(2) for a
  degree-2 common neighbour, and co-citation 1 for a single shared
  predecessor.
- Assert the composed weight equals the exact linear combination of the
  pinned coefficients for both the co-citing-hub case and the
  shared-feature-plus-tag case.
- Assert determinism (repeated computation is identical), descending-weight
  ordering, sorted endpoints, `to_dict` round-trip, and that the canonical
  DiGraph never holds a derived edge.
- Fix the root cause of a hash-seed-dependent flake: make `_extract_feature`
  pick the lexicographically smallest non-directory tag instead of an
  arbitrary set element, so feature assignment - and the derived edges that
  depend on it - is reproducible across processes.

## Outcome

Every derived signal and the composed weight are pinned by exact-value tests
over real files with no mocks: Adamic-Adar is asserted as exactly 1/ln(2), and
each composed weight as the exact coefficient sum. The 16 new tests pass, and
the full 103-test graph suite passes deterministically under several
`PYTHONHASHSEED` values; ruff, ruff-format, and ty are clean, and vault check
all stays green.

## Notes

Writing the shared-tag test surfaced a pre-existing non-determinism in
`_extract_feature`: it returned the first element of an unordered tag set, so a
document with two non-directory tags got an order-dependent feature under hash
randomisation, which silently broke the derived edges' reproducibility. The
one-line sort fixes the root cause rather than papering over it with a flaky
or tolerance-based test; it touches the graph build module beyond the test
file but is the correct fix for the determinism the derived edges promise.
