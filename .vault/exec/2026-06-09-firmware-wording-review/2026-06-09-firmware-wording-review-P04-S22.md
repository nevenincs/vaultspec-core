---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
step_id: S22
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# rewrite the persistence steps to scaffold via vaultspec-core vault add then edit body prose, removing the hand-authored frontmatter instruction (D4)

## Scope

- `src/vaultspec_core/builtins/skills/vaultspec-write/SKILL.md`

## Description

- Replace the bare plan path in the Persistence rule with a scaffold step:
  `vaultspec-core vault add plan --feature {feature} --tier <L1..L4> --related <adr-stem>`,
  then structure via the existing `vaultspec-core vault plan` verbs and author the
  Description, Parallelization, and Verification prose as body edits (D4)
- Extend the template-reading mandate to note the embedded hint blocks govern body
  structure, keeping the template's role intact
- Reword the Frontmatter & Tagging Mandate from hand-authoring imperatives to
  scaffold-produces-verify framing; `tier:` is now described as set via `--tier` at
  scaffold time and changed only through `vault plan tier promote | demote`, replacing
  the "writer adds the field on first edit" hand-edit instruction
- Align the Drafting instruction's trailing sentence: the tier is already set in
  frontmatter by the `--tier` flag rather than declared by the drafting persona
- Run mdformat --wrap 88 on the edited file

## Outcome

The vaultspec-write skill's persistence flow now matches its own CLI usage mandate end
to end: the document is born via `vault add plan`, structure flows through the
`vault plan` verbs (mandate kept verbatim), and only prose sections are authored as
body edits. The hand-authored frontmatter instructions (tier on first edit, schema
"MUST" imperatives) are gone; the tagging section describes what the scaffold produces.

## Notes

The Phase Summary and Step Record path bullets under Persistence are untouched: they
describe execute-phase artifact addressing, not this skill's authoring flow. The
literal `'#plan', '#feature'` syntax example is P08.S101 scope; the "personaa" typo is
P08.S80 scope; the divergent announce line is P08.S98 scope. None were touched.
