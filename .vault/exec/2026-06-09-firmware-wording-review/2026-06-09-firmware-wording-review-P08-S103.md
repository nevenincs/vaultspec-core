---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
step_id: S103
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# replace the literal hash-feature tag example with the hash-curly-feature convention placeholder (D15)

## Scope

- `src/vaultspec_core/builtins/skills/vaultspec-execute/SKILL.md`

## Description

- Replace the literal tag example `tags: ['#exec', '#feature']` with the convention
  placeholder form `tags: ['#exec', '#{feature}']` in the Frontmatter and Tagging
  Mandate syntax bullet
- Normalize the italic `*Feature Tag:*` label to the bold `**Feature Tag**:` form the
  sibling skills' tag-mandate blocks use
- Format the skill with mdformat at wrap 88

## Outcome

The execute skill's tag syntax example now uses the curly-brace convention placeholder
so agents substitute a real kebab-case feature tag instead of copying the literal word
"feature" verbatim, per decision D15. The Feature Tag label now carries the bold form
matching the Directory Tag bullet above it and the research, write, and curate skills'
parallel blocks. Verification grep for the literal `'#feature'` token across the file
returns zero matches.

## Notes

None.
