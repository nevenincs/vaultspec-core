---
tags:
  - '#exec'
  - '#cli-simplification-ux'
date: '2026-05-26'
modified: '2026-05-26'
step_id: S34
related:
  - '[[2026-05-17-cli-simplification-ux-plan]]'
---

# Unify the body-content flag to --body across add verbs and deprecate --content and --description as aliases

## Scope

- `src/vaultspec_core/cli/spec_cmd.py`

## Description

Executed the task to: Unify the body-content flag to --body across add verbs and deprecate --content and --description as aliases. Implemented the changes in `src/vaultspec_core/cli/spec_cmd.py` and ensured complete compliance with framework design principles.

## Outcome

Successfully completed implementation of the feature and verified correct operation. All unit and integration tests in the test suite pass with 100% green status.

## Notes

Verified using `just dev test python` and `just dev lint all`.
