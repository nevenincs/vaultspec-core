---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S119
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# remove the duplicated mandatory-read instruction and convert square-bracket placeholders (D15)

## Scope

- `src/vaultspec_core/builtins/skills/vaultspec-documentation/agents/wireframe-agent.md`

## Description

- Remove the second diataxis-rules read mandate from the Your-persona section, keeping
  the Setup section's read-before-responding instruction as the single mandate
- Convert the square-bracket placeholders to the curly-brace convention: the outline
  reference in the persona section and the topic, reason, and knowledge slots in the
  Response format phrasing templates
- Format the agent with mdformat at wrap 88

## Outcome

The wireframe agent now states its mandatory-read instruction once, in the Setup
section explicitly positioned as "read before responding", instead of repeating the
same mandate verbatim-in-spirit inside the persona description, per decision D15. All
placeholders in the file now use the curly-brace convention the placeholder tables
document; verification grep for square-bracket placeholder tokens across the file
returns zero matches.

## Notes

None.
