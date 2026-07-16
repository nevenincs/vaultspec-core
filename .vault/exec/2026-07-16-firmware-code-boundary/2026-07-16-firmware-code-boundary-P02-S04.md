---
tags:
  - '#exec'
  - '#firmware-code-boundary'
date: '2026-07-16'
modified: '2026-07-16'
step_id: 'S04'
related:
  - "[[2026-07-16-firmware-code-boundary-plan]]"
---

# Add the byte-identical boundary bullet to the core implementation mandate of all three executor personas

## Scope

- `src/vaultspec_core/builtins/agents/vaultspec-low-executor.md src/vaultspec_core/builtins/agents/vaultspec-standard-executor.md src/vaultspec_core/builtins/agents/vaultspec-high-executor.md`

## Description

- Insert the Code stands alone bullet after the Autonomous decisions bullet in the
  core implementation mandate of `vaultspec-low-executor.md`,
  `vaultspec-standard-executor.md`, and `vaultspec-high-executor.md`, byte-identical
  across the trio per the standing structural-parallelism constraint.
- Propagate with install upgrade and sync to the deployed `.vaultspec/agents/`
  snapshots.

## Outcome

Every code-writing executor persona now carries the compressed boundary echo:
deliverable code, comments, docstrings, tests, and configuration never reference the
plan, Step ids, vault documents, or harness paths; traceability lives in the Step
Record, which cites the code, never the reverse. Byte-identity verified by diffing the
extracted bullet across the three files.

## Notes

None.
