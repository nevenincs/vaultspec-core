---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S21
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# rewrite the persistence steps to scaffold via vaultspec-core vault add then edit body prose, removing the hand-authored frontmatter instruction (D4)

## Scope

- `src/vaultspec_core/builtins/skills/vaultspec-research/SKILL.md`

## Description

- Replace the "Save findings to" persistence line with a scaffold step:
  `vaultspec-core vault add research --feature {feature}`, then author the findings as
  body prose; the CLI owns the filename and frontmatter (D4)
- Rephrase the researcher instruction so the dispatched persona conducts research and
  the returned findings are written into the scaffolded document's body, dropping the
  "Persist findings to `.vault/research/...`" hand-authoring directive
- Extend the template-reading mandate to note the embedded hint blocks govern body
  structure, keeping the template's role intact
- Reword the Frontmatter & Tagging Mandate from hand-authoring imperatives to
  scaffold-produces-verify framing, matching the S20 treatment of the adr skill
- Run mdformat --wrap 88 on the edited file

## Outcome

The vaultspec-research skill now teaches the scaffold-then-edit-body-prose path instead
of hand-saving a templated document with hand-written frontmatter, removing the
contradiction with the CLI rule's prohibition on hand-writing frontmatter, filenames,
or new vault documents. The template mandate survives as the body-structure authority
and the tagging section describes what the scaffold produces.

## Notes

The literal `'#research', '#feature'` syntax example is intentionally untouched;
P08.S100 replaces it with the `#{feature}` convention placeholder. The
host-environment multi-researcher coordination sentence is untouched; P06.S53 names the
generic researcher persona there. The grammatically broken description fragment is
P08.S82 scope and was not touched.
