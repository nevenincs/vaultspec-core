---
tags:
  - '#exec'
  - '#rename-convergence'
date: '2026-06-27'
modified: '2026-06-27'
step_id: 'S08'
related:
  - "[[2026-06-27-rename-convergence-plan]]"
---

# Add real-filesystem hooks_rename tests (move plus induced-failure rollback)

## Scope

- `src/vaultspec_core/core/tests/test_hooks_rename.py`

## Description

- Add a real-filesystem test module with a fixture that builds a temporary hooks directory and sets an isolated workspace context that is reset on teardown, with no test doubles.
- Assert a successful rename moves the file and preserves its bytes exactly, since a hook rename is a pure move with no content rewrite.
- Assert rollback on an induced failure: renaming into a subdirectory whose parent does not exist fails the rename inside the transaction, leaves the source hook byte-identical, and creates no destination.
- Assert containment refuses an escaping destination and leaves the source byte-identical.
- Assert the `ResourceExistsError` collision and `ResourceNotFoundError` missing-source contract, including that a pre-existing destination is untouched on collision.

## Outcome

- Closes the standing coverage gap: `hooks_rename` had no dedicated tests; it now has five real-filesystem assertions covering the move, rollback, containment, and both contract raises.

## Notes

- No incidents. The full unit gate moved from 1503 to 1520 passing with no regressions after adding the resource and hook rename suites.
