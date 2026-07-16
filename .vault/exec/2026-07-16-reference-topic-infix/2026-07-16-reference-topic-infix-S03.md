---
tags:
  - '#exec'
  - '#reference-topic-infix'
date: '2026-07-16'
modified: '2026-07-16'
step_id: 'S03'
related:
  - "[[2026-07-16-reference-topic-infix-plan]]"
---

# Add the optional topic field to DocumentSpec converging on the same create_vault_doc call

## Scope

- `src/vaultspec_core/mcp_server/tools/documents.py`

## Description

- Add the optional `topic` field to `DocumentSpec` with the same validation and
  per-item failure semantics, converging on the same `create_vault_doc` call.

## Outcome

MCP create tool at parity with the CLI flag. Modified:
`src/vaultspec_core/mcp_server/tools/documents.py`.

## Notes

None.
