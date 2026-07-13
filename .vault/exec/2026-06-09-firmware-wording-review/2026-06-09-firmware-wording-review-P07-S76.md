---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S76
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# lowercase the uppercase YYYY-MM-DD in the hint block and reword the garbled DO-NOT-add-frontmatter-fields-outside-the-frontmatter hint (D14)

## Scope

- `src/vaultspec_core/builtins/templates/plan.md`

## Description

- Lowercase the date prefix of the wiki-link example in the FRONTMATTER RULES hint to
  the lowercase yyyy-mm-dd convention form
- Reword the garbled closing hint to "DO NOT add fields beyond those scaffolded;
  metadata lives only in the frontmatter"
- Format the template with mdformat at wrap 88

## Outcome

The plan template's FRONTMATTER RULES hint matches the lowercase date convention the
placeholder table documents, and the closing hint now states the intended
constraint. The S58 tier placeholder, S59 H1, and S61 verification-hint edits in the
same file are untouched. Template annotation and hydration tests pass (19 passed).

## Notes

None.
