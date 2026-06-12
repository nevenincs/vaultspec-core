---
tags:
  - '#exec'
  - '#vault-orientation'
date: '2026-06-12'
modified: '2026-06-12'
step_id: S12
related:
  - '[[2026-06-12-vault-orientation-plan]]'
---

# add the modified field and its frontmatter comment line to the code-review template

## Scope

- `src/vaultspec_core/builtins/templates/code-review.md`

## Description

- Add the modified frontmatter row directly after the date row in
  `src/vaultspec_core/builtins/templates/code-review.md`, using the same quoted
  placeholder style as date.
- Add a FRONTMATTER RULES comment paragraph documenting the field as the
  CLI-maintained last-modified stamp, placed after the Related paragraph.
- Format the template with mdformat at wrap 88.

## Outcome

The code-review template now carries the modified schema row per the
vault-orientation ADR decisions D3 and D3a, matching the rows added in S05 through
S11.

## Notes

None.
