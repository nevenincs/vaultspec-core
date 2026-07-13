---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S115
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# align the supersession mechanics with the unified status-section procedure (D13)

## Scope

- `src/vaultspec_core/builtins/skills/vaultspec-codify/SKILL.md`

## Description

- Rewrite the Supersede bullet in the Supersession discipline section to the unified
  procedure: a `## Status` section in both rule bodies (prior rule names the
  successor's slug, new rule names the rule it supersedes), then the existing do-not-
  silently-delete and `vaultspec-core spec rules remove <name>` steps
- Format the skill with mdformat at wrap 88

## Outcome

The codify skill's supersession discipline now matches the unified procedure decision
D13 selected and P08.S114 landed in the codify rule: both rule bodies carry a Status
section declaring the supersession relationship, and the prior rule is removed via the
CLI verb once teammates are aware. The skill's earlier variant marked only the prior
rule's body, leaving the successor silent about what it replaced. The skill's
no-first-encounter guard ("wait until the constraint has held across at least one full
execution cycle") was already present in its Do-NOT-use list and needed no change.

## Notes

None.
