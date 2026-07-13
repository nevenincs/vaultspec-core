---
tags:
  - '#exec'
  - '#install-mode'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S32'
related:
  - "[[2026-07-13-install-mode-plan]]"
---

# Run the full unit gate and fix any regressions surfaced by the mode-awareness changes

## Scope

- `src/vaultspec_core`

## Description

- Run the full unit gate:
  `pytest src/vaultspec_core -m "unit and not gemini and not claude"`.
- Confirm zero failures and zero new skips surfaced by the mode-awareness
  changes.

## Outcome

The gate passed clean: 1652 passed, 1052 deselected, 0 failed, 0 errors, no new
skips, in about 147 seconds. No regression was introduced by the P05 migration,
documentation, or reference changes, so no fix was required.

## Notes

None.
