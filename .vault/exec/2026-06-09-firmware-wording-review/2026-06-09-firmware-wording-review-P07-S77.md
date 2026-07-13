---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S77
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# lowercase the uppercase YYYY-MM-DD in the hint block and reword the garbled DO-NOT-add-frontmatter-fields-outside-the-frontmatter hint (D14)

## Scope

- `src/vaultspec_core/builtins/templates/reference.md`

## Description

- Lowercase the date prefix of the wiki-link example in the FRONTMATTER RULES hint to
  the lowercase yyyy-mm-dd convention form
- Reword the garbled closing hint to "DO NOT add fields beyond those scaffolded;
  metadata lives only in the frontmatter"
- Format the template with mdformat at wrap 88

## Outcome

The reference template's FRONTMATTER RULES hint matches the lowercase date
convention the placeholder table documents, and the closing hint now states the
intended constraint. Template annotation tests pass.

## Notes

The plan row scopes this Step to `src/vaultspec_core/builtins/templates/ref-audit.md`,
the template's filename when the plan was authored. P06.S50 renamed that file to
`src/vaultspec_core/builtins/templates/reference.md` per decision D7; this Step
applies the row's edit to the renamed file, which is the same template.
