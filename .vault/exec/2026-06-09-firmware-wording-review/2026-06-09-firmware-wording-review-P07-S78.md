---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S78
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# lowercase the uppercase YYYY-MM-DD in the hint block and reword the garbled DO-NOT-add-frontmatter-fields-outside-the-frontmatter hint (D14)

## Scope

- `src/vaultspec_core/builtins/templates/research.md`

## Description

- Lowercase the date prefix of the wiki-link example in the FRONTMATTER RULES hint to
  the lowercase yyyy-mm-dd convention form
- Reword the garbled closing hint to "DO NOT add fields beyond those scaffolded;
  metadata lives only in the frontmatter"
- Format the template with mdformat at wrap 88
- Run the full test suite as the closing check of the template sweep

## Outcome

The research template's FRONTMATTER RULES hint matches the lowercase date convention
the placeholder table documents, and the closing hint now states the intended
constraint. With this Step the S71-S78 hint sweep is complete: a grep across
`src/vaultspec_core/builtins/templates/` finds zero remaining uppercase YYYY-MM-DD
tokens and zero remaining "frontmatter fields outside the frontmatter" hints. The
full test suite passes after the last template edit of the phase: 2036 passed in
296.51s, including the template annotation, hydration, CLI language-contract, and
rule-contract suites.

## Notes

None.
