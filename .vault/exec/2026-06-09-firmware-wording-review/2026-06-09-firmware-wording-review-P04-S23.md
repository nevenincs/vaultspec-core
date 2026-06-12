---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S23
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# rewrite the persistence steps to scaffold via vaultspec-core vault add then edit body prose, removing the hand-authored frontmatter instruction (D4)

## Scope

- `src/vaultspec_core/builtins/skills/vaultspec-code-review/SKILL.md`

## Description

- Insert a scaffold step into the Workflow:
  `vaultspec-core vault add audit --feature {feature}`, with issues logged to the
  scaffolded document's body as triaged `LOW`->`CRITICAL` entries; the CLI owns the
  filename and frontmatter (D4)
- Repoint the shared-audit subagent instruction at the scaffolded document's body
  instead of a hand-addressed `.vault/audit/...` path
- Reword the Location bullet from "Must save to" to "the scaffold creates", keeping the
  optional narrative-infix disambiguation wording P01.S07 established
- Reword the Tags bullet from "Ensure persisted audit doc uses" to scaffold-produces-
  verify framing via `vaultspec-core vault check all`
- Extend the template-reading mandate to note the embedded hint blocks govern body
  structure, keeping the template's role intact
- Run mdformat --wrap 88 on the edited file

## Outcome

The code-review skill's Verify artifact is now born via `vault add audit` and grows
through body-prose appends, removing the instruction to hand-save a templated document
at a hand-written address. The canonical audit location and the narrative-infix
disambiguator from D2 are preserved as descriptions of what the scaffold produces.

## Notes

A dry-run confirmed `vault add audit --feature <tag>` produces the canonical
`yyyy-mm-dd-{feature}-audit.md` filename and that `--title` does not alter the
filename, so the narrative-infix sentence stays descriptive rather than naming a CLI
flag. The "continously" typo and the garbled rolling-log phrase on the final bullet are
P08.S81 scope and were not touched.
