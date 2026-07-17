---
tags:
  - '#exec'
  - '#mcp-testing'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S01'
related:
  - "[[2026-07-17-mcp-testing-plan]]"
---

# Ground the sweep: inventory both repos' MCP tests and amend the testing decision with the functional assertion floor

## Scope

- `.vault/adr/2026-02-22-mcp-testing-adr.md`

## Description

- Inventory core and rag MCP tests (rag via a read-only agent), classifying functional vs existence-only assertions
- Persist the inventory as the feature's research grounding
- Amend the testing decision in place with the functional assertion floor and its one degenerate exception

## Outcome

ADR amendment live; research doc records the two-repo picture.

## Notes

None.
