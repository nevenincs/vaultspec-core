---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S24
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# rewrite the persistence steps to scaffold via vaultspec-core vault add then edit body prose, removing the hand-authored frontmatter instruction (D4)

## Scope

- `src/vaultspec_core/builtins/skills/vaultspec-code-research/SKILL.md`

## Description

- Replace the "Must persist findings to" path instruction with a scaffold step:
  `vaultspec-core vault add reference --feature {feature}`, then author the findings as
  body prose; the CLI owns the filename and frontmatter (D4)
- Repoint the Research & Audit coordination bullet at the scaffolded document's body:
  blueprints land as body prose, and pre-existing documents are updated via body-prose
  edits rather than re-saved wholesale
- Run mdformat --wrap 88 on the edited file

## Outcome

The code-research skill no longer instructs hand-saving a reference document at a
hand-addressed path; the artifact is born via `vault add reference` and the findings
flow into its body. This was the only artifact-producing skill without a
frontmatter-and-tagging mandate, so nothing needed reframing; the missing template and
tagging mandates are deliberately not added here.

## Notes

P06.S52 adds the template mandate, the standard frontmatter-and-tagging mandate, and
the pointer to the reference-auditor persona; this Step confines itself to the D4
authoring-path rewrite to avoid colliding with that later scope.
