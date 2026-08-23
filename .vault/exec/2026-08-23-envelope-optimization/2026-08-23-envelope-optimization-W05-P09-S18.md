---
tags:
  - '#exec'
  - '#envelope-optimization'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:b84b70af7cd011c13ba974b788f81d31d0b077bcf5ef9dc3026338df46f00273'
step_id: 'S18'
related:
  - "[[2026-08-23-envelope-optimization-plan]]"
---

# Trim returns, raises and context prose from tool descriptions and move parameter guidance onto fields

## Scope

- `src/vaultspec_core/mcp_server/tools`

## Description

- Strip the returns, raises and context sections from tool descriptions at registration.
- Trim the spawn-contract narrative from the gateway's description.

## Outcome

The returns section restated what the output schema already carried and named Python classes the model cannot see. The raises section described exceptions it never observes, since a protocol error arrives as an error result rather than a traceback. And the request context was documented in eight of nine argument blocks while appearing in no input schema, so it described an argument the caller cannot pass; two tools spent a sentence explaining it was unused.

## Notes

This was done to pay for contract fields added elsewhere rather than raise a ceiling. The first attempt made the description larger: it replaced narrative with a paragraph explaining where the narrative had gone, which itself ships on every turn. The rationale belongs in a source comment, not in the docstring.
