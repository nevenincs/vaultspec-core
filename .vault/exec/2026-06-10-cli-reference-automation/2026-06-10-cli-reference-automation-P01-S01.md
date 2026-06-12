---
tags:
  - '#exec'
  - '#cli-reference-automation'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S01
related:
  - '[[2026-06-10-cli-reference-automation-plan]]'
---

# Add a removal-milestone marker to the legacy template-name fallback so the ref-audit.md grace path is scheduled for removal one release after the rename, keeping the existing five fallback tests green (REVIEW-005 fallback)

## Scope

- `src/vaultspec_core/vaultcore/hydration.py`

## Description

- Add a removal-milestone TODO marker above the `_LEGACY_TEMPLATE_NAMES` module
  constant in `hydration.py`, scheduling the `ref-audit.md` grace path for removal
  one release after the renamed `reference.md` first ships.
- Add a matching TODO marker on the legacy fallback branch inside
  `get_template_path` so the two halves of the transitional code are removed together.
- Record the rationale: the `ref-audit.md` to `reference.md` rename has not shipped
  in a published release yet (current version 0.1.26), so the grace path must survive
  at least one upgrade cycle before deletion.

## Outcome

The legacy-filename fallback now carries an explicit removal milestone in both the
module constant and the resolver branch. Behavior is unchanged: the current-name
template is still preferred, the legacy fallback still emits its upgrade warning, and
the both-missing path still returns `None`. The five existing fallback hydration tests
stay green (21 passed in the targeted suite); ruff and ty report no findings.

## Notes

- Why: the firmware-wording-review code review left REVIEW-005 as a LOW note asking
  for the transitional fallback to be scheduled for removal rather than left to linger
  indefinitely. The marker makes the removal trigger discoverable to a future agent.
- Origin: REVIEW-005 (LOW) in the `firmware-wording-review` audit, tracked as plan
  Step P01.S01.
- No behavior change, so no new tests were required; the existing fallback coverage is
  the regression guard.
