---
tags:
  - '#exec'
  - '#cli-simplification-ux'
date: '2026-05-26'
modified: '2026-06-13'
body_hash: 'sha256:f4a7b4b35d9cd48326d8d9c12a4b841b6afe21142a65b16010bbf07cabd76b80'
step_id: S40
related:
  - '[[2026-05-17-cli-simplification-ux-plan]]'
---

# Add --force requirement on destructive sub-paths within additive verbs such as install --upgrade

## Scope

- `src/vaultspec_core/cli/root.py`

## Description

Executed the task to: Add --force requirement on destructive sub-paths within additive verbs such as install --upgrade. Implemented the changes in `src/vaultspec_core/cli/root.py` and ensured complete compliance with framework design principles.

## Outcome

Successfully completed implementation of the feature and verified correct operation. All unit and integration tests in the test suite pass with 100% green status.

## Notes

Verified using `just dev test python` and `just dev lint all`.
