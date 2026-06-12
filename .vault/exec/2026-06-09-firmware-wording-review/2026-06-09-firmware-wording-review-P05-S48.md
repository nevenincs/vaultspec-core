---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S48
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# add the audit-report persistence obligation that the curate skill already promises (D11)

## Scope

- `src/vaultspec_core/builtins/agents/vaultspec-docs-curator.md`

## Description

- Add an "Audit Report Persistence" section to the persona: scaffold via
  `vaultspec-core vault add audit --feature docs-curation` (CLI owns filename and
  frontmatter), then author the findings - violations found, fixes applied or
  delegated, flagged Recommendations - into the scaffolded body directly, since this
  persona carries Write and Edit (D11)
- Extend the Final Output to link the persisted audit report alongside the
  "Audit Complete" summary
- Run mdformat --wrap 88 on the edited file

## Outcome

The docs-curator persona now carries the audit-report persistence obligation its
dispatching skill has promised since the curate skill's Review section was written;
the research finding that the persona "persists nothing" is closed. D11 is complete:
the skill describes the delegate model (S47) and the persona persists the report
(S48). This also completes Phase P05 (S27-S48).

## Notes

The persona persists the report body itself rather than returning it to an
orchestrator: unlike the S27-S29 read-only personas, the curator is `mode: read-write`
with Write and Edit, so the body-prose edit after the `vault add` scaffold is within
its own declared contract (consistent with the S30 mode-field definition).
