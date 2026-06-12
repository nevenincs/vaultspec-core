---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S86
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# normalize the three bold-label conventions to the single Label-colon-sentence mandate form (D15)

## Scope

- `src/vaultspec_core/builtins/system/01-core.md`

## Description

- Normalize the lowercase-verb label "Do Not revert changes:" to the Title Case "Do
  Not Revert Changes:" matching every sibling label
- Convert the bold-full-sentence row "Do NOT go beyond the scope of a feature." to the
  labeled form "Feature Scope:" with the original sentence as body text
- Convert the bold-phrase-mid-sentence row "Never accept tautological tests, and
  avoid mocks..." to the labeled form "Test Integrity:" with the original sentences as
  body text
- Convert the structurally identical bold-phrase row "Never add skips to linting and
  type checking..." to the labeled form "Lint and Type-Check Integrity:" with a
  semicolon joining its two clauses
- Format the fragment with mdformat at wrap 88

## Outcome

Every Core Mandates bullet now opens with one convention: a Title Case bold label
terminated by a colon inside the bold span, followed by sentence prose. The three
competing bold-label conventions the research identified are collapsed to one per
decision D15; a structural grep of the bullet heads confirms all thirteen rows match
the Label-colon-sentence form. The mid-sentence emphasis spans inside bullet bodies
(for example "ask for confirmation first") are untouched, as they are emphasis rather
than labels.

## Notes

The "Never add skips" row shared the bold-phrase convention with the "Never accept
tautological tests" row, so it is normalized in the same pass; leaving it divergent
would have defeated the single-convention goal of the Step.
