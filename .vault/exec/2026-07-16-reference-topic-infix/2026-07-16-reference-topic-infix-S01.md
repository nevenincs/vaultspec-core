---
tags:
  - '#exec'
  - '#reference-topic-infix'
date: '2026-07-16'
modified: '2026-07-16'
step_id: 'S01'
related:
  - "[[2026-07-16-reference-topic-infix-plan]]"
---

# Add the optional topic parameter to create_vault_doc with the infixed filename for audit, reference, and research and a hard error for other types

## Scope

- `src/vaultspec_core/vaultcore/hydration.py`

## Description

- Add the optional topic parameter to `create_vault_doc`: infixed filename
  `{date}-{feature}-{topic}-{type}.md` for the narrative trio, `ValueError` for
  any other type, omitted topic byte-identical to prior behavior.

## Outcome

Filename authority extended in one place; exists- and stem-collision guards
apply unchanged on the infixed path. Modified:
`src/vaultspec_core/vaultcore/hydration.py`.

## Notes

None.
