---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
step_id: S98
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# normalize the divergent announce line to the canonical form (D15)

## Scope

- `src/vaultspec_core/builtins/skills/vaultspec-write/SKILL.md`

## Description

- Replace the divergent Rules bullet "Announce: Explicitly state you are starting the
  planning phase." with the canonical quoted form "Announce at start: I'm using the
  vaultspec-write skill to write the implementation plan.", matching the
  Announce-at-start pattern the sibling skills carry
- Format the skill with mdformat at wrap 88

## Outcome

The write skill's announce line now follows the canonical quoted Announce-at-start
form per decision D15. With S96, S97, and this Step, every top-level skill that
announces does so in one pattern: a bold "Announce at start:" label followed by a
quoted first-person sentence naming the skill in backticks. Verification grep for
"Announce" in the file returns only the canonical line.

## Notes

None.
