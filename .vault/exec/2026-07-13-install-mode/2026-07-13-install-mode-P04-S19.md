---
tags:
  - '#exec'
  - '#install-mode'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S19'
related:
  - "[[2026-07-13-install-mode-plan]]"
---

# Add the mode_mismatch field to WorkspaceDiagnosis and wire it through the diagnose orchestrator

## Scope

- `src/vaultspec_core/core/diagnosis/diagnosis.py`

## Description

- Import `ModeMismatchSignal` into the diagnosis module.
- Add the `mode_mismatch` field to `WorkspaceDiagnosis`, defaulting to `ModeMismatchSignal.CLEAN`, with a docstring entry.
- Thread a `mode_mismatch` local through `diagnose()` and pass it into the `WorkspaceDiagnosis` constructor, mirroring the existing `rename_integrity` local-var-then-construct pattern.

## Outcome

`WorkspaceDiagnosis` now carries a mode-mismatch axis alongside the other signal fields, and `diagnose()` populates it from a local variable so the concrete collector can be dropped in without further constructor changes. This step keeps the value pinned to `CLEAN`; the real comparison against the persisted declaration and the observed hook and MCP shapes is wired in the next step. Collector tests stay green (58 passed), confirming the added field and constructor argument do not disturb existing diagnosis paths.

## Notes

The `mode_mismatch` local is intentionally a placeholder `CLEAN` this step rather than a call to `collect_mode_mismatch_state`, which does not yet exist; splitting the field-and-threading from the collector keeps each commit independently green. Following the always-collected-signal convention, the eventual probe is designed to degrade to `CLEAN` on failure rather than raise, so diagnosis never crashes on a malformed workspace.
