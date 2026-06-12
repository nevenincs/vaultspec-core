---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S43
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# align the Documentation section to the trio-parallel form referencing the exec-step.md template (D9)

## Scope

- `src/vaultspec_core/builtins/agents/vaultspec-standard-executor.md`

## Description

- Add the three trio-parallel sub-bullets under the DOCUMENT CONCISELY mandate -
  **Template** (`templates/exec-step.md`), **Linking** (wiki-links in `related:`
  only), and **Content** (modified files plus concise summary of key changes) -
  matching the S42 low-executor base verbatim (D9)
- Run mdformat --wrap 88 on the edited file

## Outcome

The standard executor's Documentation contract now carries the same template pointer,
linking obligation, and content checklist as the low executor; previously only the
low executor referenced the `exec-step.md` template.

## Notes

The introductory DOCUMENT CONCISELY paragraph was already identical across the trio
and was not touched.
