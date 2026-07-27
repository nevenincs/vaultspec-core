---
tags:
  - '#exec'
  - '#adr-topic-infix'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S01'
related:
  - "[[2026-07-27-adr-topic-infix-plan]]"
---

# Extend the shared topic-infix admission set to ADR documents

## Scope

- `src/vaultspec_core/vaultcore/hydration.py`

## Description

- Extend the shared admission set with `DocType.ADR`.
- Preserve the existing filename builder and collision authority.
- Align the creator-level admitted-types diagnostic.

## Outcome

The shared scaffolder can now select the existing topic-infix filename path for
ADRs. CLI and MCP boundary changes remain in their dedicated Steps.

## Notes

No data migration or compatibility change is required because omitted topics retain
their existing filename path.
