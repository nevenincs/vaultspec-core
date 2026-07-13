---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S64
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# annotate the heading, scope_block, step_id, and plan_stem placeholders as machine-filled (D14)

## Scope

- `src/vaultspec_core/builtins/templates/exec-step.md`

## Description

- Extend the FRONTMATTER RULES hint to note that the step_id and plan_stem
  placeholders are machine-filled by the exec scaffolding verb
- Extend the STEP RECORD hint to note that the heading and scope_block placeholders
  are machine-filled from the originating Step row and must not be filled by hand
- Format the template with mdformat at wrap 88

## Outcome

All four snake_case placeholders the research flagged as undefined are now annotated
as machine-filled inside hint comments, matching the hydration implementation, which
substitutes exactly these four tokens when scaffolding a Step Record. The
placeholders themselves are not renamed: the hydration code fills them by literal
token, so renaming would be a behavioral change outside this documentation-only
feature. The named-class documentation in the placeholder conventions is S69's row.
Template annotation and hydration tests pass (19 passed).

## Notes

None.
