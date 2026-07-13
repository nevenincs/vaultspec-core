---
tags:
  - '#exec'
  - '#vault-orientation'
date: '2026-06-12'
modified: '2026-06-13'
step_id: S06
related:
  - '[[2026-06-12-vault-orientation-plan]]'
---

# add the modified field and its frontmatter comment line to the reference template

## Scope

- `src/vaultspec_core/builtins/templates/reference.md`

## Description

- Add the modified frontmatter row directly after the date row in
  `src/vaultspec_core/builtins/templates/reference.md`, using the same quoted
  placeholder style as date.
- Add a FRONTMATTER RULES comment line documenting the field as the CLI-maintained
  last-modified stamp: set at scaffold time, refreshed by mutating CLI verbs and vault
  check fix, never hand-edited.
- Format the template with mdformat at wrap 88.

## Outcome

The reference template now carries the modified schema row per the vault-orientation
ADR decisions D3 and D3a, matching the row added to the research template in S05.
Scaffold-time injection from W01.P01 skips the field when the template carries it, so
no duplicate row is emitted.

## Notes

None.
