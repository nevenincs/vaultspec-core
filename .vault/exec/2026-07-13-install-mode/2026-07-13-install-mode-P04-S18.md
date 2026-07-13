---
tags:
  - '#exec'
  - '#install-mode'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S18'
related:
  - "[[2026-07-13-install-mode-plan]]"
---

# Add the ModeMismatchSignal enum with CLEAN, MISMATCH, and UNKNOWN members

## Scope

- `src/vaultspec_core/core/diagnosis/signals.py`

## Description

- Add the `ModeMismatchSignal` string enum next to `RenameIntegritySignal`, with `CLEAN`, `MISMATCH`, and `UNKNOWN` members.
- Document `UNKNOWN` as the legacy pre-install-mode bridge case (no persisted declaration to compare against), explicitly not a warning.

## Outcome

The diagnosis signal vocabulary now carries a dedicated axis for install-mode coherence. `CLEAN` means the persisted declaration and the observed artifacts agree or there is nothing to compare; `MISMATCH` means the declaration names one mode but the hook entries or MCP launch are shaped for the other; `UNKNOWN` means no mode is persisted yet. The enum is inert this step - no collector, diagnosis field, or resolver rule reads it until the following steps wire it through.

## Notes

The `UNKNOWN` member deliberately maps to the same operational meaning as `CLEAN` (no flag raised): a workspace with no committed declaration predates the decision and is bridged to dependency-shaped expectations elsewhere, so holding its artifacts against a declared mode it never made would be a false positive.
