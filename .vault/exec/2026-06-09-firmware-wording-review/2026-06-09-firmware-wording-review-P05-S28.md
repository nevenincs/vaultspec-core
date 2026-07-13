---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S28
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# reword the persistence mandate to return findings to the dispatching orchestrator, which persists via vault add scaffold plus body-prose edit, keeping the persona read-only (D3)

## Scope

- `src/vaultspec_core/builtins/agents/vaultspec-adr-researcher.md`

## Description

- Rewrite the Persistence section: the persona is read-only and does not write the
  research document to disk; it returns the complete findings to the dispatching
  orchestrator, which persists them by scaffolding
  `vault add research --feature <feature>` and editing the scaffolded body prose (D3)
- Reword the Research Report Format's "MUST read and use the template" imperative into
  "structure your returned findings on the template" so the template stays the shape
  contract for the returned message
- Retitle the Frontmatter & Tagging Mandate to "Frontmatter & Tagging Schema
  (orchestrator-owned)" and reword its imperatives into a description of the
  scaffold-produced frontmatter
- Keep the canonical research destination as a description of where the orchestrator
  persists, and scope the linking rule to persisted documents
- Run mdformat --wrap 88 on the edited file

## Outcome

The adr-researcher's declared `mode: read-only` and its body now agree: the persona
returns `<Research>` findings instead of saving them, and the persistence path
(scaffold via `vault add research`, then body-prose edit) lives with the dispatching
orchestrator, mirroring the S27 code-reviewer contract.

## Notes

The "context enhancer ... focus solely on gathering" restriction in the Important
section was deliberately left untouched; its reconciliation with the persona's
formalizes-decisions description is P05.S45 (D10). Frontmatter was not touched.
