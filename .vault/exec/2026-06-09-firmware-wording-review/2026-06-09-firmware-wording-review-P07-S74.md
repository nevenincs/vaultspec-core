---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
body_hash: 'sha256:d17ae0c6b39186dc870a9d5b8e93181eb6c32e4b4f2e7863db911dd4b3b15474'
step_id: S74
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# lowercase the uppercase YYYY-MM-DD in the hint block and reword the garbled DO-NOT-add-frontmatter-fields-outside-the-frontmatter hint (D14)

## Scope

- `src/vaultspec_core/builtins/templates/exec-step.md`

## Description

- Lowercase the date prefix of the parent-plan wiki-link example in the FRONTMATTER
  RULES hint to the lowercase yyyy-mm-dd convention form
- Reword the garbled closing hint to "DO NOT add fields beyond those scaffolded;
  metadata lives only in the frontmatter"
- Format the template with mdformat at wrap 88

## Outcome

The exec-step template's FRONTMATTER RULES hint matches the lowercase date
convention the placeholder table documents, and the closing hint now states the
intended constraint. The machine-filled annotations added in S64 are untouched.
Template annotation tests pass.

## Notes

None.
