---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S59
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# drop the stale phase segment from the H1 heading, a fossil of the one-plan-per-phase model (D14)

## Scope

- `src/vaultspec_core/builtins/templates/plan.md`

## Description

- Replace the plan template H1 scaffold with the phase-less form, removing the
  backticked phase segment between the feature segment and the word "plan"
- Format the template with mdformat at wrap 88

## Outcome

The plan template H1 no longer carries the `{phase}` segment: a plan spans all phases
under the tier model, and the plan filename pattern has no phase segment either, so
the heading now matches both. Hydration needed no change: the `{phase}` token was
only an alias of `{title}` and remains in use by the exec-summary template; nothing
in the plan template references it any longer. Template annotation and hydration
tests pass (19 passed). The rules' heading example that canonizes the old
phase-bearing form is updated separately in S60, per the row split.

## Notes

None.
