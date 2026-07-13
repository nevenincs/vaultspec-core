---
tags:
  - '#exec'
  - '#vault-orientation'
date: '2026-06-12'
modified: '2026-06-13'
step_id: S09
related:
  - '[[2026-06-12-vault-orientation-plan]]'
---

# add the modified field and its frontmatter comment line to the exec-step template

## Scope

- `src/vaultspec_core/builtins/templates/exec-step.md`

## Description

- Add the modified frontmatter row between the date and step_id rows in
  `src/vaultspec_core/builtins/templates/exec-step.md`, using the same quoted
  placeholder style as date.
- Add a FRONTMATTER RULES comment paragraph documenting the field as the
  CLI-maintained last-modified stamp, placed between the tags and step_id paragraphs.
- Format the template with mdformat at wrap 88.

## Outcome

The exec-step template now carries the modified schema row per the vault-orientation
ADR decisions D3 and D3a. Records scaffolded by vault add exec already carried the
stamp via the W01.P01 injection; the template now declares it as schema.

## Notes

None.
