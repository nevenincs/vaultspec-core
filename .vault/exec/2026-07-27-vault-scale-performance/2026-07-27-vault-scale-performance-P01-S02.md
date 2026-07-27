---
tags:
  - '#exec'
  - '#vault-scale-performance'
date: '2026-07-27'
modified: '2026-07-27'
body_schema: 'body-v1'
step_id: 'S02'
related:
  - "[[2026-07-27-vault-scale-performance-plan]]"
---

# add a cheap descriptive-counts surface and route the render_tree title through it, keeping graph-theoretic metrics opt-in

## Scope

- `src/vaultspec_core/graph/api.py`

## Description

- Add `GraphCounts` and a `counts()` surface producing the document,
  link, and feature totals without any graph-theoretic algorithm.
- Route the tree render title through `counts()`; export the new
  class from the graph package.
- Add tests asserting counts equal the metrics triple and, via a real
  profiler, that render paths never invoke centrality.

## Outcome

Tree titles are byte-identical to the conflated path; expensive
analysis is strictly opt-in; 3 new tests pass.

## Notes

The `--metrics` flag and the JSON envelope remain the explicit
opt-in analysis surfaces by design.
