---
tags:
  - '#exec'
  - '#adr-topic-infix'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:96b3e06dda3eb8664212353984a41b481008f457b6a2094cde9ccc9dfe4a07a7'
step_id: 'S04'
related:
  - "[[2026-07-27-adr-topic-infix-plan]]"
---

# Cover direct scaffolder creation and duplicate rejection for topic-infixed ADRs

## Scope

- `src/vaultspec_core/vaultcore/tests/test_hydration.py`

## Description

- Add ADR to the direct admitting-type coverage.
- Keep plan and execution records in the rejection coverage.
- Reproduce two same-day ADR topics and duplicate rejection.

## Outcome

The direct scaffolder regression suite proves that two distinct ADR topics create
separate records while an identical topic remains blocked by the existing guard.

## Notes

`src/vaultspec_core/vaultcore/tests/test_hydration.py` passed: 32 tests.
