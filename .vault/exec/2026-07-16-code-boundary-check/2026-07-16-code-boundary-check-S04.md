---
tags:
  - '#exec'
  - '#code-boundary-check'
date: '2026-07-16'
modified: '2026-07-16'
step_id: 'S04'
related:
  - "[[2026-07-16-code-boundary-check-plan]]"
---

# Regenerate the bundled CLI reference and confirm the drift test

## Scope

- `src/vaultspec_core/builtins/reference/cli.md`

## Description

- Regenerate the bundled CLI reference and the docs CLI page so the generated
  inventory carries the new verb; roll out to the deployed mirror through the
  owning CLI path.

## Outcome

Drift suite green (22 tests). Note: the reference-drift pre-commit hook makes
the verb, its tests, and the regenerated reference atomic, so S02-S04 landed
in one consolidated commit.

## Notes

None.
