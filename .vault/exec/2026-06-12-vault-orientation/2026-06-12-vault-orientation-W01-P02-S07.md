---
tags:
  - '#exec'
  - '#vault-orientation'
date: '2026-06-12'
modified: '2026-06-12'
step_id: S07
related:
  - '[[2026-06-12-vault-orientation-plan]]'
---

# add the modified field and its frontmatter comment line to the adr template

## Scope

- `src/vaultspec_core/builtins/templates/adr.md`

## Description

- Add the modified frontmatter row directly after the date row in
  `src/vaultspec_core/builtins/templates/adr.md`, using the same quoted placeholder
  style as date.
- Add a FRONTMATTER RULES comment line documenting the field as the CLI-maintained
  last-modified stamp, placed between the Related and Status convention paragraphs.
- Format the template with mdformat at wrap 88.

## Outcome

The adr template now carries the modified schema row per the vault-orientation ADR
decisions D3 and D3a, matching the rows added in S05 and S06. Supersession-driven
stamp refresh lands separately in W01.P03.

## Notes

None.
