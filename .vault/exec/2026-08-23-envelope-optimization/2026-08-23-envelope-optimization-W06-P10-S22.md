---
tags:
  - '#exec'
  - '#envelope-optimization'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:d43dd231d8a4837f835ee01b17d43fe301358aaa3c2d07059646a3fc306bf0bb'
step_id: 'S22'
related:
  - "[[2026-08-23-envelope-optimization-plan]]"
---

# Add a scaling regression guard asserting repair stays linear in document count

## Scope

- `src/vaultspec_core/tests`

## Description

- Add a guard asserting the repair pipeline's graph builds do not grow with the feature count.
- Add a guard asserting the index generator does not disable the cache.

## Outcome

The defect this guards is invisible to a correctness test - the preview returned the right answer, just eventually - and invisible on a small fixture, where a handful of rebuilds finish quickly. So it counts the work rather than timing it: a wall-clock threshold would be flaky on a loaded machine and would say nothing about why it regressed.

## Notes

Verified to fail rather than merely to pass: with the defect reintroduced the guard reports fourteen builds over twelve features and names the cause.

The first version counted builds by substituting the builder, which the repository-health guards forbid outright - tests must exercise real code paths. It now counts the builder's own log line, which is strictly better: it observes the real pipeline instead of a replacement.
