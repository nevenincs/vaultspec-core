---
tags:
  - '#exec'
  - '#install-mode'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S05'
related:
  - "[[2026-07-13-install-mode-plan]]"
---

# Extend the manifest tests with the ManifestData resolved_mode and resolved_floor_version echo fields, covering read, write, and legacy-manifest backward compatibility

## Scope

- `src/vaultspec_core/tests/cli/test_manifest_v2.py`

## Description

- Add a `TestModeEcho` class to the manifest test module covering the new
  `resolved_mode` and `resolved_floor_version` echo fields with real filesystem
  round trips (no mocks, stubs, or skips).
- Assert the write round trip persists and re-reads both echo fields, serializes
  the mode as its string value, and serializes an unset mode and floor as JSON
  `null`.
- Assert legacy backward compatibility: a manifest written before mode-awareness
  reads back with both echo fields `None`, and a malformed mode token reads as
  `None` rather than raising.
- Assert the echo survives an `add_providers` read-modify-write cycle.

## Outcome

Twenty-three manifest tests pass, the six new ones plus the seventeen preexisting
ones unchanged, confirming the echo fields are additive and never regress the
existing v2.0 manifest contract. The legacy-manifest and malformed-token cases
pin the backward-compatible read the ADR Q1 split requires: the gitignored echo
is best-effort bookkeeping, so a missing or bad value degrades to `None` rather
than failing the read.

## Notes

No incidents. The manifest echo is deliberately lenient (unlike the strict
committed declaration read in S04) because it is per-machine bookkeeping, not the
authoritative source of truth.
