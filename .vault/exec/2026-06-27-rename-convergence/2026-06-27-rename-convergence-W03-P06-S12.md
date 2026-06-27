---
tags:
  - '#exec'
  - '#rename-convergence'
date: '2026-06-27'
modified: '2026-06-27'
step_id: 'S12'
related:
  - "[[2026-06-27-rename-convergence-plan]]"
---

# Add concurrency-safety tests asserting serialized renames cause no lost update or partial state

## Scope

- `src/vaultspec_core/vaultcore/tests/test_rename_concurrency.py`

## Description

- Add a deterministic, real-filesystem, mock-free concurrency suite using threading events and a shared block-then-complete probe.
- Prove the docs sentinel serializes two acquirers via an ordered event log, where the second acquire is recorded strictly after the first release.
- Prove the structure cascade acquires the sentinel by holding it in one thread and asserting `check_structure` with fix blocks until release, then completes the rename and ref-rewrite.
- Prove the document rename acquires the sentinel by holding it and asserting `_execute_rename` blocks until release, then completes with a consistent final state and no lost update.

## Outcome

- Three tests assert serialization deterministically: a bounded wait confirms the second caller is blocked while the lock is held, and the holder releases only after that assertion, so the second caller's completion is strictly ordered after release.
- The suite passed five consecutive runs with no flakiness and final on-disk state is asserted consistent in each case.

## Notes

- ContextVars do not propagate to spawned threads, so the rename worker establishes its own workspace context before driving the real verb. The data directory is materialized in each fixture so the advisory lock actually engages rather than no-opping.
