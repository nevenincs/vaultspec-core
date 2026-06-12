---
tags:
  - '#exec'
  - '#graph-backend'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S31
related:
  - '[[2026-06-10-graph-backend-plan]]'
---

# add cache correctness tests proving a stale cache is never trusted

## Scope

- `src/vaultspec_core/graph/tests/test_cache.py`

## Description

- Added correctness tests over a function-scoped on-disk synthetic vault with stem
  collisions, a cycle, and phantom links, with no mocks, patches, or sleeps.
- Proved a body edit that grows the file is reflected in the next build and is not the
  cached word count, and that validation reports the cache stale after the edit.
- Proved a same-byte-length edit that changes only the content hash is rejected by
  validation and reflected in the next build, exercising the case the bare size and
  mtime guard could miss within one timestamp tick.
- Proved an added file appears and a removed file disappears in the next build, driven
  by file-set divergence.
- Proved a truncated cache file and an empty cache file both degrade to a full rebuild
  that reproduces the fresh node and edge counts and rewrites a valid cache.
- Proved a cache hit reconstructs a graph whose body-bearing JSON export, node set,
  edge attributes, per-node pagerank and in-degree, and dangling links all match a
  forced fresh build exactly.
- Proved that adding an edge through the link add verb drops the cache file and that
  the next build reflects the new edge.

## Outcome

Nine tests pass and encode stale-never-trusted as exact assertions rather than
trivially-true conditions: each staleness trigger asserts both that validation rejects
the cache and that the rebuilt graph carries the new bytes, and the identity test
compares the cached build against a forced no-cache build rather than against itself.
Lint and type checks are clean.

## Notes

The same-size-edit test is the load-bearing soundness proof: it constructs the exact
pathological case the fast-path size and mtime guard cannot distinguish, and asserts
the content hash catches it. Expected values are derived from the fixture (original word
count plus the appended word count, the flipped title string) rather than copied from a
prior run, so a regression that served stale data fails rather than passing quietly.
