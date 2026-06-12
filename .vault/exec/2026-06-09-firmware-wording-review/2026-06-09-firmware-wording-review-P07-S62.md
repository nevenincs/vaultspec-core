---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S62
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# lowercase the Title Case H1 to match the all-lowercase heading convention every sibling follows (D14)

## Scope

- `src/vaultspec_core/builtins/templates/code-review.md`

## Description

- Lowercase the code-review template H1 from the Title Case "Code Review" to "code
  review", keeping the backticked feature segment
- Format the template with mdformat at wrap 88

## Outcome

The code-review template H1 now follows the all-lowercase heading convention every
sibling template uses. The uppercase ad-hoc body placeholders in the same file are
S63's row and are untouched here. Template annotation tests pass.

## Notes

None.
