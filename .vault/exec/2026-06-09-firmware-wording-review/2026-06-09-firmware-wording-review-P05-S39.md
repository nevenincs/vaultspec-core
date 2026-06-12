---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S39
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# move the frontmatter tier MEDIUM to STANDARD if the code-binding check clears (D9)

## Scope

- `src/vaultspec_core/builtins/agents/vaultspec-project-coordinator.md`

## Description

- Move the frontmatter `tier: MEDIUM` to `tier: STANDARD`, cleared by the S34
  code-binding verdict (UNBOUND) (D9)
- Run mdformat --wrap 88 on the edited file

## Outcome

The project-coordinator persona now carries the unified middle-tier enum value
`STANDARD`, consistent with the S35 standard-executor rename.

## Notes

Frontmatter-only change; the body (extended with the Bash-only mutation note in S31)
was not touched.
