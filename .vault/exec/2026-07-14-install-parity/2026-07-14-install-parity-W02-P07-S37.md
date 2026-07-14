---
tags:
  - '#exec'
  - '#install-parity'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S37'
related:
  - "[[2026-07-14-install-parity-plan]]"
---

# Run rag's full test gate covering the new mode, renderer, and doctor tests

## Scope

- `src/vaultspec_rag/tests`

## Description

- Run the full `vaultspec-rag` unit gate (`pytest src/vaultspec_rag -m unit`)
  against the `0.1.39` core floor, including the new mode, renderer, and doctor
  tests.
- Run `ruff check`, `ruff format --check`, and `ty check` across the changed rag
  sources and confirm the complexity gate.

## Outcome

The gate reports `1348 passed, 1 skipped, 1 failed, 688 deselected`. The single
failure is the known Windows-host-only `TestWinShutdownLog::test_service_stop_skips_log_on_posix`,
a POSIX-path test that cannot pass on a `win32` host; everything else is green,
including all install-mode and doctor tests added in this phase. `ruff check` and
`ty check` pass across `src/vaultspec_rag`; the touched files are `ruff format`
clean; the complexity gate passed at commit time on every changed file.

## Notes

`ruff format --check` reports six pre-existing unformatted files elsewhere in the
rag test tree (for example `test_preprocess_runner.py`, `test_server.py`); none
were touched by this phase, and the prek format hook only inspects staged files,
so they do not gate the branch. Flagged for a separate cleanup rather than folded
into this change set.
