---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S66
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# seed the related field instead of the empty list that violates the always-populate hint the template itself states (D14)

## Scope

- `src/vaultspec_core/builtins/templates/audit.md`

## Description

- Replace `related: []` in the audit template frontmatter with the seeded wiki-link
  placeholder list every sibling template carries
- Format the template with mdformat at wrap 88

## Outcome

The audit template is no longer the sole template seeding an empty `related:` list
against the always-populate rule its own hint states: its frontmatter now carries
the same `'[[{yyyy-mm-dd-*}]]'` placeholder entry as the adr, plan, research,
reference, exec-step, and exec-summary templates. Scaffolding is unaffected because
the hydration `related:` injection pattern matches both the inline empty list and
the list-item form. Template annotation and hydration tests pass (19 passed).

## Notes

None.
