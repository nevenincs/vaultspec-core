---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S37
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# move the frontmatter tier MEDIUM to STANDARD if the code-binding check clears (D9)

## Scope

- `src/vaultspec_core/builtins/agents/vaultspec-docs-curator.md`

## Description

- Move the frontmatter `tier: MEDIUM` to `tier: STANDARD`, cleared by the S34
  code-binding verdict (UNBOUND) (D9)
- Run mdformat --wrap 88 on the edited file

## Outcome

The docs-curator persona now carries the unified middle-tier enum value `STANDARD`,
consistent with the S35 standard-executor rename.

## Notes

Frontmatter-only change; the body was not touched (the curator's audit-persistence
obligation is P05.S48, the doubled-phrasing fix is P08.S110).
