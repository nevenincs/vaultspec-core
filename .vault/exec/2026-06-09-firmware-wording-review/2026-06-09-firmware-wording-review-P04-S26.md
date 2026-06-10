---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
step_id: S26
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# qualify the absolute hand-writing mandate at line 14 to match the allowed-manual-edits section it currently contradicts (D4)

## Scope

- `src/vaultspec_core/builtins/rules/vaultspec-cli.builtin.md`

## Description

- Replace the absolute "Do not edit `.vault/` documents directly" sentence in the
  Mandate with a qualified prohibition: never hand-write frontmatter, filenames, plan
  structure, or new `.vault/` documents, while body-prose edits of documents scaffolded
  by `vaultspec-core vault add` are permitted, with a pointer at the "Allowed manual
  edits" section (D4)
- Run mdformat --wrap 88 on the edited file

## Outcome

The CLI rule no longer contradicts itself: the Mandate's prohibition now states the
same boundary as the "Allowed manual edits" section (forbidden: frontmatter, filenames,
new documents; permitted: body prose of scaffolded documents), and it now also matches
the scaffold-then-edit-body-prose authoring path the six skills rewritten in S20-S25
teach. Plan structure is named in the prohibition because the plan-editing CLI verbs
own identifier-affecting changes per the plan-hardening convention.

## Notes

The Forbidden list under "Allowed manual edits" already read correctly and was not
touched; only the Mandate paragraph changed. This closes the internal-contradiction
half of the research's hand-authoring finding; the skill-side half closed in S20-S25.
