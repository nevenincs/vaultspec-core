---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S20
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# rewrite the persistence steps to scaffold via vaultspec-core vault add then edit body prose, removing the hand-authored frontmatter instruction (D4)

## Scope

- `src/vaultspec_core/builtins/skills/vaultspec-adr/SKILL.md`

## Description

- Replace the "MUST save document to" persistence step with a scaffold step:
  `vaultspec-core vault add adr --feature {feature} --related <research-stem>`, then
  author body prose; the CLI owns the filename and frontmatter (D4)
- Extend the template-reading mandate to note the embedded hint blocks govern body
  structure, keeping the template's role intact
- Reword the Frontmatter & Tagging Mandate from hand-authoring imperatives ("MUST
  contain", "MUST use") to scaffold-produces-verify framing: the scaffold produces the
  schema, drift is reported via `vaultspec-core vault check all`, `related:` is seeded
  by the `--related` flag, `date:` is set by the scaffold
- Run mdformat --wrap 88 on the edited file

## Outcome

The vaultspec-adr skill no longer instructs hand-authoring a `.vault/adr/` document
from the template with hand-written frontmatter, which contradicted the CLI rule's
prohibition on hand-writing frontmatter, filenames, or new vault documents. The skill
now teaches the scaffold-then-edit-body-prose path; the template mandate survives as
the body-structure authority and the tagging section as a description of what the
scaffold produces.

## Notes

The scaffold flags were verified against the live `vault add --help` (the `--related`
flag accepts stems and resolves them to wiki-link format). The literal `'#adr', '#feature'` syntax example is intentionally untouched; P08.S99 replaces it with the
`#{feature}` convention placeholder. The `vaultspec-writer` drafting reference in the
Workflow section is P05.S46 scope and was not touched.
