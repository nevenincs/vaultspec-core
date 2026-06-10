---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
step_id: S51
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# unify the reference noun across the hierarchy node, the pipeline phase wording, and the directory-table description (D7)

## Scope

- `src/vaultspec_core/builtins/rules/vaultspec.builtin.md`

## Description

- Rename the Documentation Hierarchy phase-1 node from "Research / Reference Audit" to
  "Research / Reference", dropping the last "Reference Audit" compound and giving the
  three phase-1 artifact kinds parallel bold markup
- Reword the `#reference` row description in the Directory Tags table from "Reference
  audits and blueprints" to "Implementation references and blueprints", matching the
  workflow document list's "The implementation Reference" phrasing
- Format with mdformat at wrap 88

## Outcome

The "reference" noun is now unified across this rules file: the workflow document
list, the hierarchy node, and the directory-table description all describe one doc
type called Reference living in `.vault/reference/` under tag `#reference`, matching
the renamed `reference.md` template from S50. A grep of the file confirms zero
remaining "Reference Audit" / "reference audit" compounds.

## Notes

The file's phase-1 wording (the document list entry rewritten by P01 and this
hierarchy node) is the pipeline-facing wording this rules file carries; the pipeline
table itself lives in `system/03-vaultspec.md`, where the Verify row was already
corrected in P01.S04 and the phase named "1 Reference" already uses the bare noun.
No edits outside this file were needed.
