---
tags:
  - '#exec'
  - '#mcp-testing'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S03'
related:
  - "[[2026-07-17-mcp-testing-plan]]"
---

# Upgrade the entrypoint tests: handshake through the stdout-purity queue, EOF exit proven from a serving session, zero-input EOF kept as the documented exception

## Scope

- `tests/mcp/test_mcp_entrypoint.py`

## Description

- Extend the startup test with an initialize round-trip through the stdout-purity queue
- Split EOF coverage: serving-session disconnect (handshake then close stdin) and zero-input EOF kept as the documented floor exception

## Outcome

Committed as `9caa4f48`.

## Notes

None.
