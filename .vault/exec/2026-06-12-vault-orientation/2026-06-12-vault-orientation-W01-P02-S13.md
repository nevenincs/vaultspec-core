---
tags:
  - '#exec'
  - '#vault-orientation'
date: '2026-06-12'
modified: '2026-06-13'
step_id: S13
related:
  - '[[2026-06-12-vault-orientation-plan]]'
---

# add the modified field and its frontmatter comment line to the index template

## Scope

- `src/vaultspec_core/builtins/templates/index.md`

## Description

- Add the modified frontmatter row directly after the date row in
  `src/vaultspec_core/builtins/templates/index.md`, using the same quoted placeholder
  style as date.
- Document the field inside the FEATURE INDEX comment, the index template's only
  guidance block, since it carries no FRONTMATTER RULES comment.
- Format the template with mdformat at wrap 88.

## Outcome

The index template now carries the modified schema row per the vault-orientation ADR
decisions D3 and D3a, completing the template schema rollout across all nine shipped
templates. The vaultcore suite (242 passed) and the rule contract suite (7 passed)
are green after the full Phase.

## Notes

The index template differs from the other eight in two ways: it carries
generated true frontmatter and no FRONTMATTER RULES block, so the stamp
documentation line lives in the FEATURE INDEX comment instead.
