---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S71
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# lowercase the uppercase YYYY-MM-DD in the hint block and reword the garbled DO-NOT-add-frontmatter-fields-outside-the-frontmatter hint (D14)

## Scope

- `src/vaultspec_core/builtins/templates/adr.md`

## Description

- Lowercase the wiki-link example in the FRONTMATTER RULES hint to the
  '\[[yyyy-mm-dd-foo-bar]\]' convention form
- Reword the garbled closing hint to "DO NOT add fields beyond those scaffolded;
  metadata lives only in the frontmatter"
- Format the template with mdformat at wrap 88

## Outcome

The adr template's FRONTMATTER RULES hint now uses the lowercase `{yyyy-mm-dd}`
convention form the placeholder table documents, and the closing hint states the
intended constraint instead of the self-contradictory original. Template annotation
tests pass.

## Notes

None.
