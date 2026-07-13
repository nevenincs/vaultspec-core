---
tags:
  - '#exec'
  - '#vault-orientation'
date: '2026-06-12'
modified: '2026-06-13'
step_id: S08
related:
  - '[[2026-06-12-vault-orientation-plan]]'
---

# add the modified field and its frontmatter comment line to the plan template

## Scope

- `src/vaultspec_core/builtins/templates/plan.md`

## Description

- Add the modified frontmatter row between the date and tier rows in
  `src/vaultspec_core/builtins/templates/plan.md`, using the same quoted placeholder
  style as date.
- Add a FRONTMATTER RULES comment paragraph documenting the field as the
  CLI-maintained last-modified stamp, placed between the tags and tier paragraphs.
- Format the template with mdformat at wrap 88.

## Outcome

The plan template now carries the modified schema row per the vault-orientation ADR
decisions D3 and D3a. The scaffolded plan frontmatter still parses through the
emit-time plan validator since modified is an additive field. Plan-serialiser stamp
refresh lands separately in W01.P03.

## Notes

None.
