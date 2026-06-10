---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
step_id: S69
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# document the machine-filled placeholder class (heading, step_id, plan_stem, scope_block, document_list) as a named class in the placeholder conventions (D14)

## Scope

- `src/vaultspec_core/builtins/rules/vaultspec.builtin.md`

## Description

- Add a Machine-Filled Placeholders subsection to the Placeholder Naming Conventions
  between the Document Body Placeholders table and the General Rules
- Table the five machine-filled placeholders with the owning CLI verb and the value
  each receives; state the snake_case naming distinction and the
  never-fill-or-rename-by-hand contract
- Format with mdformat at wrap 88

## Outcome

The five snake_case placeholders the research flagged as undefined are now a named,
documented class in the conventions: `{heading}`, `{step_id}`, `{plan_stem}`, and
`{scope_block}` filled by the exec scaffolding verb, `{document_list}` filled by the
feature-index verb. The naming convention (snake_case marks machine-filled,
kebab-case and prose mark author-replaced) is stated so future templates stay
distinguishable. This completes the conventions side of the annotations added to the
templates in S64 and S68. Template annotation and rule contract tests pass (10
passed).

## Notes

None.
