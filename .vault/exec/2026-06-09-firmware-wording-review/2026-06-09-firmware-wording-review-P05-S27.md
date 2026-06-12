---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S27
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# reword the persistence mandate to return findings to the dispatching orchestrator, which persists via vault add scaffold plus body-prose edit, keeping the persona read-only (D3)

## Scope

- `src/vaultspec_core/builtins/agents/vaultspec-code-reviewer.md`

## Description

- Replace the Workflow's "Write a review report" bullet with "Return the complete
  review report as your final message"
- Rewrite the Persistence section: the persona is read-only and does not write the
  report to disk; it returns the report to the dispatching orchestrator, which
  persists it by scaffolding `vault add audit --feature <feature>` and editing the
  scaffolded body prose (D3)
- Keep the template pointer (the returned report is structured on
  `templates/code-review.md`) and the canonical audit destination with the D2
  narrative-infix disambiguator as descriptions of where the orchestrator persists
- Retitle the Frontmatter & Tagging Mandate to "Frontmatter & Tagging Schema
  (orchestrator-owned)" and reword its imperatives into a description of the
  scaffold-produced frontmatter
- Run mdformat --wrap 88 on the edited file

## Outcome

The code-reviewer persona's declared `mode: read-only` and its body now agree: the
persona returns findings instead of persisting them, and the persistence path
(scaffold via `vault add audit`, then body-prose edit) lives with the dispatching
orchestrator. The artifact path and schema knowledge are retained as descriptive
reference so the returned report needs no rework before persistence.

## Notes

The frontmatter (`tier: HIGH`, `mode: read-only`, tools without Write/Edit) was not
touched; D3 keeps the verification gate read-only by design. The Severity Taxonomy and
Critical Output sections already described message-level outputs and needed no change.
