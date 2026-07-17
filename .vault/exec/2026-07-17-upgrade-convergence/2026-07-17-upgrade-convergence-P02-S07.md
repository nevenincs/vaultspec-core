---
tags:
  - '#exec'
  - '#upgrade-convergence'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S07'
related:
  - "[[2026-07-17-upgrade-convergence-plan]]"
---

# Cover migration idempotence on both modes and both advisories with real-workspace tests

## Scope

- `src/vaultspec_core/tests`

## Description

- Add migration tests driving real provisioned workspaces in both render
  modes: legacy entry converges on migrate, the second run is a byte-level
  no-op, hand-edited entries survive with a skipped count, and a workspace
  without recorded enrollment creates nothing.
- Add advisory tests: prek.toml plus stale YAML hooks reports the
  unrefreshable signal (without prek.toml the existing signal is
  preserved), the stale-seed collector names static builtin seeds while
  ignoring tokenized seeds and custom definitions, and both advisories
  leave the doctor exit code at zero.

## Outcome

Eleven tests passing against real files; no mocks, stubs, or skips.

## Notes

None.
