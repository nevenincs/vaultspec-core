---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
step_id: S120
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# reword the start-with-phase instruction so it holds at l1 where only steps exist (D15)

## Scope

- `src/vaultspec_core/builtins/skills/vaultspec-execute/SKILL.md`

## Description

- Reword the dispatch bullet from 'Always instruct to "Start with Phase P##."' to the
  tier-conditional entry point: Step S## at L1 (Steps only), Phase P## at L2, and the
  canonical display path (e.g., W01.P01) at L3 / L4
- Format the skill with mdformat at wrap 88

## Outcome

The execute skill's dispatch instruction now holds at every tier, per decision D15. The
previous wording mandated a Phase entry point unconditionally, which is impossible at
L1 where Phases do not exist; the bullet now names the entry point per tier, matching
the tier model the system fragment documents (L1 Steps only, L2 adds Phases, L3/L4 add
Waves and the display path). Verification: the file contains no remaining unconditional
"Start with Phase" instruction.

## Notes

None.
