---
tags:
  - '#exec'
  - '#markdown-feature-scope'
date: '2026-07-27'
modified: '2026-07-27'
body_schema: 'body-v1'
step_id: 'S04'
related:
  - "[[2026-07-27-markdown-feature-scope-plan]]"
---

# Add an opt-in migration-control parameter that preserves the default scanner contract

## Scope

- `src/vaultspec_core/vaultcore/scanner.py`

## Description

- Add a keyword-only scanner switch that defaults to the established lazy-migration behavior.
- Guard the pending-migration trigger with that switch while leaving document discovery unchanged.

## Outcome

Existing scanner callers retain migration convergence by default; callers with an explicit no-unrelated-mutation boundary can opt out.

## Notes

The existing lazy-trigger integration tests remained green.
