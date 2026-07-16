---
tags:
  - '#exec'
  - '#firmware-code-boundary'
date: '2026-07-16'
modified: '2026-07-16'
step_id: 'S08'
related:
  - "[[2026-07-16-firmware-code-boundary-plan]]"
---

# Run vault check all, prek hooks, and the unit test gate, fixing any drift the gates surface

## Scope

- `src/vaultspec_core`

## Description

- Run `vaultspec-core vault check all` and rebuild the stale feature index it flagged.
- Run the unit test gate `pytest src/vaultspec_core -m unit`.
- Run the plan's verification greps: boundary phrasing sweep across the builtins and
  the byte-identity hash of the executor-trio bullet.

## Outcome

Unit gate green: 1760 passed, 1051 deselected, 281s. Vault check reports only the
three pre-existing warnings on unrelated features. prek hooks passed on every commit
in the change set. The boundary-phrasing grep matches exactly the eight decided files
(six surfaces; the executor trio is three files), and the trio bullet hashes identical
across all three personas. No drift required fixing beyond the feature-index rebuild.

## Notes

None.
