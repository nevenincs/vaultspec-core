---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S87
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# replace the project-bondedness neologism with project-bound, repair the verb-less back-pointer sentence, and order the tool list (D15)

## Scope

- `src/vaultspec_core/builtins/agents/vaultspec-codifier.md`

## Description

- Replace the neologism sentence "The bar is durability, constraint-shape, and
  project-bondedness." with "The bar is that the lesson is durable,
  constraint-shaped, and project-bound.", matching the persona's own three named
  criteria
- Repair the verb-less sentence ending "the back-pointer structures." to "the
  back-pointer becomes structured frontmatter."
- Reorder the frontmatter tools list to the convention order Glob, Grep, Read, Write,
  Edit, Bash
- Format the persona with mdformat at wrap 88

## Outcome

The codifier persona's bar statement now uses the same project-bound vocabulary as
its durability-criteria list, the supersession paragraph ends in a grammatical
sentence, and the tools list matches the convention order the sibling personas carry,
per decision D15. Verification grep for `project-bondedness` and `back-pointer structures` returns zero matches.

## Notes

The British spelling "centre" in the Supersession discipline section is left in place
deliberately; the plan assigns it to the dedicated spelling sweep Step S91 on this
same file.
