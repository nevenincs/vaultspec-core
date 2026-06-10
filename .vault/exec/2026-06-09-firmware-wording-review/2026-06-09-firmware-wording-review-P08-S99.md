---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
step_id: S99
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# replace the literal hash-feature tag example with the hash-curly-feature convention placeholder (D15)

## Scope

- `src/vaultspec_core/builtins/skills/vaultspec-adr/SKILL.md`

## Description

- Replace the literal tag example `tags: ['#adr', '#feature']` with the convention
  placeholder form `tags: ['#adr', '#{feature}']` in the Frontmatter and Tagging
  Mandate syntax bullet
- Format the skill with mdformat at wrap 88

## Outcome

The adr skill's tag syntax example now uses the curly-brace convention placeholder so
agents substitute a real kebab-case feature tag instead of copying the literal word
"feature" verbatim, per decision D15. Verification grep for the literal `'#feature'`
token across the file returns zero matches; the surrounding Feature Tag bullet
already used the `#{feature}` form, so the section is now internally consistent.

## Notes

None.
