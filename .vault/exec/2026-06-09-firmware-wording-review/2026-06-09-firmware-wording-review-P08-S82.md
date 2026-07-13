---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S82
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# repair the grammatically broken description fragment (D15)

## Scope

- `src/vaultspec_core/builtins/skills/vaultspec-research/SKILL.md`

## Description

- Rewrite the frontmatter description from the broken fragment "Use it when unsure
  about how to proceed with a complex feature, refactor, or debugging task and need
  to explore options before implementation, structured research and brainstorm." to
  the grammatical "Use this skill for structured research and brainstorming when
  unsure how to proceed with a complex feature, refactor, or debugging task and
  options need exploring before implementation."
- Format the skill with mdformat at wrap 88

## Outcome

The frontmatter description now reads as one grammatical sentence naming the skill's
subject (structured research and brainstorming) up front, resolving the
typo-inventory item per decision D15. Verification grep for the dangling fragment
"structured research and brainstorm." returns zero matches.

## Notes

None.
