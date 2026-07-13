---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S109
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# fix the doubled the-dot-vault-vault phrasing (D15)

## Scope

- `src/vaultspec_core/builtins/skills/vaultspec-curate/SKILL.md`

## Description

- Rephrase "audit and clean the .vault vault" in the frontmatter description to "audit
  and clean the .vault/ documentation vault"
- Format the skill with mdformat at wrap 88

## Outcome

The curate skill's frontmatter description no longer doubles the word "vault" against
the directory name, per decision D15. The new phrasing matches the body's existing "the
`.vault/` documentation vault" form in the skill's opening paragraph, so the
description and body now use one noun phrase for the artifact store. Verification grep
for the doubled phrasing across the file returns zero matches.

## Notes

None.
