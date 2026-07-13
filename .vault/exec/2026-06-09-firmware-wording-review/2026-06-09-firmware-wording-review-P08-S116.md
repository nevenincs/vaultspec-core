---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S116
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# align the supersession mechanics with the unified status-section procedure (D13)

## Scope

- `src/vaultspec_core/builtins/agents/vaultspec-codifier.md`

## Description

- Rewrite the Supersede bullet in the persona's Supersession discipline section to the
  unified procedure: a `## Status` section in both rule bodies (prior rule names the
  successor's slug, new rule names the rule it supersedes), then
  `vaultspec-core spec rules remove <name>` once teammates are aware
- Keep the planned `superseded_by:` frontmatter field as a parenthetical forward
  pointer
- Format the persona with mdformat at wrap 88

## Outcome

The codifier persona's supersession discipline now matches the unified procedure
decision D13 selected and P08.S114/S115 landed in the codify rule and skill. The
persona's earlier variant ("mark the prior rule's status as superseded in its body")
named no Status section, no successor back-pointer, and no removal step; all three are
now present, so the codify trio states one procedure end to end. The persona's
no-first-encounter guard was already present in its CRITICAL RULES list and needed no
change.

## Notes

None.
