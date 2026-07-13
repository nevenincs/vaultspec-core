---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S38
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# move the frontmatter tier MEDIUM to STANDARD if the code-binding check clears (D9)

## Scope

- `src/vaultspec_core/builtins/agents/vaultspec-reference-auditor.md`

## Description

- Move the frontmatter `tier: MEDIUM` to `tier: STANDARD`, cleared by the S34
  code-binding verdict (UNBOUND) (D9)
- Run mdformat --wrap 88 on the edited file

## Outcome

The reference-auditor persona now carries the unified middle-tier enum value
`STANDARD`, consistent with the S35 standard-executor rename.

## Notes

Frontmatter-only change; the body (rewritten for persistence in S29) was not touched.
The snapshot-template and retired-persona fixes remain P06.S56 and P06.S57.
