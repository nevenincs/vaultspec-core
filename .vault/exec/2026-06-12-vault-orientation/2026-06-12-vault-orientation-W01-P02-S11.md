---
tags:
  - '#exec'
  - '#vault-orientation'
date: '2026-06-12'
modified: '2026-06-13'
step_id: S11
related:
  - '[[2026-06-12-vault-orientation-plan]]'
---

# add the modified field and its frontmatter comment line to the audit template

## Scope

- `src/vaultspec_core/builtins/templates/audit.md`

## Description

- Add the modified frontmatter row directly after the date row in
  `src/vaultspec_core/builtins/templates/audit.md`, using the same quoted placeholder
  style as date.
- Add a FRONTMATTER RULES comment paragraph documenting the field as the
  CLI-maintained last-modified stamp, placed after the Related paragraph.
- Format the template with mdformat at wrap 88.

## Outcome

The audit template now carries the modified schema row per the vault-orientation ADR
decisions D3 and D3a. Rule-promotion stamp refresh on the source audit lands
separately in W01.P03.

## Notes

None.
