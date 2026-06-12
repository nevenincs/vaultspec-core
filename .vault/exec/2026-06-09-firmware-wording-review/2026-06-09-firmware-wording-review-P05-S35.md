---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S35
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# rename the medium-tier description wording to standard and move the frontmatter tier MEDIUM to STANDARD if the code-binding check clears (D9)

## Scope

- `src/vaultspec_core/builtins/agents/vaultspec-standard-executor.md`

## Description

- Rename the frontmatter description's "Medium-tier implementation specialist" to
  "Standard-tier implementation specialist" (D9)
- Move the frontmatter `tier: MEDIUM` to `tier: STANDARD`, cleared by the S34
  code-binding verdict (UNBOUND: the value is dropped by every renderer and never
  parsed or asserted) (D9)
- Run mdformat --wrap 88 on the edited file

## Outcome

The middle executor tier now carries one name across all three surfaces: filename
(`vaultspec-standard-executor`), description ("Standard-tier"), and frontmatter
(`tier: STANDARD`), eliminating the three-way naming drift the research inventoried.

## Notes

The body's H1 already read "(Standard-Tier)" and needed no change. The remaining five
`tier: MEDIUM` personas move in S36-S40; the full test suite runs once after S40.
