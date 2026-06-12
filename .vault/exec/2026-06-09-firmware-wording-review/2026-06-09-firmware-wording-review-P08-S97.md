---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S97
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# add the canonical announce line the skill lacks (D15)

## Scope

- `src/vaultspec_core/builtins/skills/vaultspec-team/SKILL.md`

## Description

- Add the canonical announce line after the opening paragraph: "I'm using the
  vaultspec-team skill to coordinate a team of agent personas.", using the standalone
  bold-label paragraph form that the research, documentation, projectmanager, and
  curate skills carry
- Format the skill with mdformat at wrap 88

## Outcome

The team skill now carries the canonical announce line per decision D15, closing the
second of the two announce-line gaps the research found. With S96 and this Step, all
eleven top-level skills either carry the canonical Announce-at-start line or are
normalized by Step S98 (the write skill's divergent form). Verification grep for
"Announce at start" in the file returns the new line.

## Notes

None.
