---
tags:
  - '#exec'
  - '#graph-backend'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S33
related:
  - '[[2026-06-10-graph-backend-plan]]'
---

# register the dedicated benchmark marker

## Scope

- `pyproject.toml`

## Description

- Registered the benchmark marker in the pytest marker list with a description matching
  the existing marker style.
- Added a pytest addopts marker expression that deselects the benchmark marker so the
  default test run does not execute the scale benchmarks.

## Outcome

The default pytest run deselects all four benchmark cases, and an explicit benchmark
marker selection collects exactly those four with no unknown-marker warning. The TOML
manifest passes taplo lint.

## Notes

The default suite previously had no marker-based deselection, so a fresh addopts marker
expression was introduced rather than extending an existing one; it deselects only the
benchmark marker, leaving every other marker running by default exactly as before. The
benchmarks remain runnable on demand by passing the benchmark marker explicitly.
