---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
step_id: S114
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# unify the supersession procedure and add the execution-cycle guard (D13)

## Scope

- `src/vaultspec_core/builtins/rules/vaultspec-codify.builtin.md`

## Description

- Rewrite the Supersede bullet in the When-a-rule-itself-becomes-wrong section to the
  unified procedure: a `## Status` section in both rule bodies (prior rule names the
  successor's slug, new rule names the rule it supersedes), then
  `vaultspec-core spec rules remove <name>` once teammates are aware
- Keep the planned structured-supersession mechanism as a parenthetical forward pointer
  at the `cli-memory-lifecycle` ADR
- Add the no-first-encounter guard to the When-to-codify section: a lesson qualifies
  only after it has held across at least one full execution cycle
- Format the rule with mdformat at wrap 88

## Outcome

The codify rule now states the single supersession procedure decision D13 selected (a
Status section naming the successor in both rule bodies, then the removal verb once
teammates are aware), replacing the vaguer "mark the prior rule with a superseded
status" phrasing that drifted from the skill's and persona's variants. The rule also
carries the execution-cycle guard the persona and skill already stated, so all three
codify-trio surfaces now name the same codification bar: cross-session,
constraint-shaped, project-bound, and held across at least one full execution cycle.

## Notes

P08.S115 and P08.S116 align the skill's and the persona's supersession wording to this
unified procedure.
