---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S68
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# document the generated frontmatter field the template declares (D14)

## Scope

- `src/vaultspec_core/builtins/templates/index.md`

## Description

- Extend the FEATURE INDEX hint comment to document the generated frontmatter field
  as the machine-generated marker owned and rewritten by the feature-index command,
  and note that the document_list placeholder is machine-filled by the same command
- Format the template with mdformat at wrap 88

## Outcome

The previously undocumented `generated:` frontmatter field is now explained where
the template declares it: it marks the index as machine-generated and forbids hand
authoring, matching the never-author-by-hand guidance the rules already state for
feature indexes. The placeholder-conventions documentation of the machine-filled
class, including `{document_list}`, is S69's row in the rules file and is kept out
of this template-scoped edit. Template annotation tests pass.

## Notes

None.
