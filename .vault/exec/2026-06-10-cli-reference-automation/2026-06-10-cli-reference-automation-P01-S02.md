---
tags:
  - '#exec'
  - '#cli-reference-automation'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S02
related:
  - '[[2026-06-10-cli-reference-automation-plan]]'
---

# Relocate the in-function current-name template mapping to module scope beside \_LEGACY_TEMPLATE_NAMES for symmetry, keeping tests green (REVIEW-005 fallback)

## Scope

- `src/vaultspec_core/vaultcore/hydration.py`

## Description

- Lift the current-name template filename dictionary out of `get_template_path` into
  a module-scope constant named `_TEMPLATE_NAMES`, placed directly above
  `_LEGACY_TEMPLATE_NAMES` so the current and legacy filename maps sit together.
- Replace the in-function `mapping` local with a lookup against the new
  `_TEMPLATE_NAMES` constant, leaving the rest of the resolver untouched.

## Outcome

The current-name and legacy-name template maps now live side by side at module scope,
giving the resolver a single symmetric pair of lookup tables. This is a pure
refactor: the resolved paths, the current-name preference, the legacy fallback, and
the both-missing `None` return are all identical. The 21 targeted hydration tests pass
unchanged; ruff and ty are clean.

## Notes

- Why: the firmware-wording-review code review (REVIEW-005, LOW) noted the asymmetry
  of an in-function current-name map alongside a module-scope legacy map. Co-locating
  the two makes the transitional code easier to read and to remove together once the
  legacy fallback's milestone lands.
- Origin: REVIEW-005 (LOW) in the `firmware-wording-review` audit, tracked as plan
  Step P01.S02.
- No behavior change, so the existing hydration coverage is the regression guard; no
  new tests were added.
