---
tags:
  - '#exec'
  - '#graph-backend'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S16
related:
  - '[[2026-06-10-graph-backend-plan]]'
---

# add exact-value tests for multiplicity, edge attributes, and normalised weights on the synthetic corpus

## Scope

- `src/vaultspec_core/graph/tests/test_graph.py`

## Description

- Add a crafted on-disk vault helper where one document cites a target three
  times in its body (kind body, multiplicity 3, the graph maximum) and
  references a second target once in body and once in related (kind both,
  multiplicity 2), yielding hand-derivable exact attributes.
- Assert exact `kind`, `multiplicity`, and `weight` values: `body`/3/1.0 and
  `both`/2/(2/3), that exactly one edge normalises to weight 1.0, and that
  exactly two edges are built.
- Add a real assertion over the synthetic corpus that every explicit edge is
  kind `related`, multiplicity 1, weight 1.0, because the generator wires only
  non-duplicated `related:` frontmatter.

## Outcome

The edge-attribute schema is now pinned by exact-value tests over real files
with no mocks: the weight `2/3` is asserted as exact division, not a tolerance.
The 76 tests in the file pass (6 new); ruff and ruff-format are clean.

## Notes

The session synthetic corpus only exercises `related`/mult-1/weight-1.0 edges
because the generator emits no body wiki-links and no duplicates, so the
body, both, multiplicity>1, and sub-unit weight cases are covered by the
crafted vault rather than by contriving the shared corpus. Both paths use real
on-disk documents and real graph builds.
