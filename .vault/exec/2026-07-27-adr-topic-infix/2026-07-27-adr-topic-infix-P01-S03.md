---
tags:
  - '#exec'
  - '#adr-topic-infix'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:c8f9182c3a5365445081bafdf0bea1c3dbdad29b3f0aa881223a4879a62f6d93'
step_id: 'S03'
related:
  - "[[2026-07-27-adr-topic-infix-plan]]"
---

# Align MCP topic schema and validation with ADR admission

## Scope

- `src/vaultspec_core/mcp_server/tools/documents.py`

## Description

- Add ADR to the MCP topic field contract.
- Admit ADR specs in the per-item validation path.
- Preserve one normalized handoff to the shared creator.

## Outcome

MCP batch creation now accepts a topic-infixed ADR and reports unsupported document
types with the same four-type admission contract as the CLI and creator.

## Notes

The per-item failure behavior for unsupported types remains unchanged.
