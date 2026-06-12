---
tags:
  - '#exec'
  - '#vault-orientation'
date: '2026-06-12'
modified: '2026-06-12'
step_id: S05
related:
  - '[[2026-06-12-vault-orientation-plan]]'
---

# add the modified field and its frontmatter comment line to the research template

## Scope

- `src/vaultspec_core/builtins/templates/research.md`

## Description

- Add the modified frontmatter row directly after the date row in
  `src/vaultspec_core/builtins/templates/research.md`, using the same quoted
  placeholder style as date.
- Add a FRONTMATTER RULES comment line documenting the field as the CLI-maintained
  last-modified stamp: set at scaffold time, refreshed by mutating CLI verbs and vault
  check fix, never hand-edited.
- Format the template with mdformat at wrap 88.

## Outcome

The research template now carries the modified schema row per the vault-orientation
ADR decisions D3 and D3a. A hydration probe confirms the placeholder in the modified
line is substituted at scaffold time exactly like the date line, and the
scaffold-time injection added in W01.P01 skips templates that already carry the
field, so no duplicate row is emitted. The vaultcore suite (242 passed) and the rule
contract suite (7 passed) are green.

## Notes

A dry-run of vault add research previews only the target path, not the rendered
content, so placeholder substitution was verified with a direct hydration probe over
the updated template file instead.
