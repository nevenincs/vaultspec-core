---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S55
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# add vaultspec-team, vaultspec-projectmanager, vaultspec-code-review, and vaultspec-curate to the skill catalog, closing the catalog gaps (D8)

## Scope

- `src/vaultspec_core/builtins/rules/vaultspec.builtin.md`

## Description

- Add `vaultspec-code-review`, `vaultspec-curate`, `vaultspec-team`, and
  `vaultspec-projectmanager` to the "Where appropriate, use the following skills"
  catalog
- Reorder the catalog to read pipeline-first (research, code-research, adr, write,
  execute, code-review, codify) followed by the supporting skills (curate,
  documentation, team, projectmanager), matching the pipeline and supporting-skills
  tables in the system prompt
- Format with mdformat at wrap 88

## Outcome

The rules-file skill catalog now lists all eleven shipped skills, closing the catalog
gaps the research inventoried: the minor-finding omissions (`vaultspec-code-review`,
`vaultspec-curate`) and the orphaned-member omissions (`vaultspec-team`,
`vaultspec-projectmanager`). Every directory under
`src/vaultspec_core/builtins/skills/` now appears in at least one catalog surface.

## Notes

None.
