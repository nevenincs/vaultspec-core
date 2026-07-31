---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
body_hash: 'sha256:c0139d2f6ef96f799765dae10c22cbe2cebc7be9d2a42775e86eaf289cce4b05'
step_id: S96
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# add the canonical announce line the skill lacks (D15)

## Scope

- `src/vaultspec_core/builtins/skills/vaultspec-execute/SKILL.md`

## Description

- Add the canonical announce line as the first Required Steps bullet: "I'm using the
  vaultspec-execute skill to execute the implementation plan.", matching the exact
  Announce-at-start bold-label pattern the sibling skills carry
- Format the skill with mdformat at wrap 88

## Outcome

The execute skill now carries the canonical announce line per decision D15, closing
one of the two announce-line gaps the research found (the other is the team skill,
Step S97). Verification grep for "Announce at start" in the file returns the new
line; the wording follows the sibling pattern of quoting the skill name in backticks
inside the announced sentence.

## Notes

None.
