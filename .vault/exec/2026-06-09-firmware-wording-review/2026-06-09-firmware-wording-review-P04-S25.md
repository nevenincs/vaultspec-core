---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S25
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# rewrite the persistence steps to scaffold via vaultspec-core vault add then edit body prose, removing the hand-authored frontmatter instruction (D4)

## Scope

- `src/vaultspec_core/builtins/skills/vaultspec-curate/SKILL.md`

## Description

- Replace the bare audit-report path with a scaffold step:
  `vaultspec-core vault add audit --feature docs-curation`, findings persisted into the
  scaffolded document's body; the CLI owns the filename and frontmatter (D4)
- Prefer CLI repair paths over hand edits across the fix flow: the dispatch
  instruction now says "Repair violations through `vaultspec-core vault check all --fix` and the CLI repair paths rather than hand edits", the Auto-fixed report bucket
  names `vault check all --fix` as the fixer, and the Non-destructive requirement
  describes repair through the CLI fix paths instead of direct renames and
  frontmatter/link edits
- Reword the skill description's "Fixes violations in-place" to "Fixes violations
  through the CLI repair paths"
- Reframe the Frontmatter & Tagging Mandate lead-in as the validation schema the
  curator checks: the scaffold produces conforming frontmatter for new documents and
  `vault check all --fix` repairs violations in existing ones
- Run mdformat --wrap 88 on the edited file

## Outcome

The curate skill's fix flow and audit-report persistence now route through the CLI:
the report is born via `vault add audit` and grows as body prose, and every repair
instruction prefers `vault check all --fix` over the direct renames and frontmatter
edits the skill previously implied. The schema bullets survive as validation criteria
rather than hand-authoring instructions.

## Notes

The curator-versus-delegate contract reconciliation (whether the persona edits at all
or orchestrates fixes through loaded personas) is P05.S47 scope and was deliberately
not addressed; this Step only moved the fix mechanics onto the CLI surface. The
"the .vault vault" doubled phrasing in the description is P08.S109 scope and the
literal directory-tag syntax example is P08.S102 scope; neither was touched.
