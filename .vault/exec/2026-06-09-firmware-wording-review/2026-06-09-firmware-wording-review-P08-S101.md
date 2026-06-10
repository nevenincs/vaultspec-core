---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
step_id: S101
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# replace the literal hash-feature tag example with the hash-curly-feature convention placeholder (D15)

## Scope

- `src/vaultspec_core/builtins/skills/vaultspec-write/SKILL.md`

## Description

- Replace the literal tag example `tags: ['#plan', '#feature']` with the convention
  placeholder form `tags: ['#plan', '#{feature}']` in the Frontmatter and Tagging
  Mandate syntax bullet
- Normalize the underscore-emphasis `_Syntax:_` label to the asterisk form `*Syntax:*`
  used by the sibling skills' tag-mandate blocks
- Format the skill with mdformat at wrap 88

## Outcome

The write skill's tag syntax example now uses the curly-brace convention placeholder so
agents substitute a real kebab-case feature tag instead of copying the literal word
"feature" verbatim, per decision D15. The syntax bullet's emphasis style now matches
the asterisk form the research, curate, and execute skills use in the same block.
Verification grep for the literal `'#feature'` token across the file returns zero
matches.

## Notes

The neighboring `_Constraint:_` and `_For plan documents:_` labels outside the
tag-mandate syntax bullet were left untouched; the step scope covers the tag example
bullet only.
