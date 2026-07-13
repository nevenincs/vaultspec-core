---
tags:
  - '#exec'
  - '#install-mode'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S21'
related:
  - "[[2026-07-13-install-mode-plan]]"
---

# Add a resolution step for ModeMismatchSignal.MISMATCH with a fix hint pointing at install --upgrade or an explicit --mode re-run, and reword the non-canonical precommit warning to be mode-aware

## Scope

- `src/vaultspec_core/core/resolver.py`

## Description

- Import `ModeMismatchSignal` into the resolver.
- Add `_resolve_mode_mismatch`, which appends an advisory warning naming both remediation commands (`install --upgrade` and an explicit `--mode` re-run) when the signal is `MISMATCH`, and no-ops for `CLEAN` and `UNKNOWN`.
- Call `_resolve_mode_mismatch` from `resolve()` alongside the other workspace-level rules, feeding the existing `ResolutionPlan` rather than a bespoke check path.
- Add an `expected_entry_prefix` parameter to `_resolve_precommit` and reword the `NON_CANONICAL` advisory to name that prefix instead of the hardcoded `uv run --no-sync vaultspec-core`.
- Resolve `expected_entry_prefix` in `resolve()` from `entry_prefix_for_mode(resolve_render_mode(target))`, falling back to the dependency-mode prefix when the mode cannot be read.

## Outcome

The resolver now reconciles two mode-aware surfaces through its existing plan machinery. A workspace whose provisioned artifacts contradict its declared mode receives a non-blocking warning pointing at the reconcile commands, and the non-canonical hook advisory now names the prefix appropriate to the workspace's resolved mode, so a drifted tool-mode workspace is told to move toward the uvx form rather than the uv-run form. Resolver tests stay green (45 passed).

The mismatch handling is deliberately advisory (a warning, not an auto-applied step), because reconciling a mode drift re-provisions the workspace and is an explicit operator decision; auto-rewriting artifacts on a plain sync would silently override the drift the operator may need to inspect first.

## Notes

The doctor command does not surface this warning: `resolve()` short-circuits to an empty plan for the `DOCTOR` action, and `cmd_doctor` renders the diagnosis directly through `_render_diagnosis_table` and `_doctor_exit_code` in `cli/spec_cmd.py`. Those two functions do not yet read the new `mode_mismatch` field, so a mismatch is currently visible only on `install`, `sync`, and `upgrade` flows, not on `doctor`. Wiring the doctor table row and exit-code weighting for `mode_mismatch` falls outside this Step's declared scope (`resolver.py`); it is flagged for the P05 Q1-Q6 review to close, since ADR Q6 names `doctor` as a surface for the mismatch check.
