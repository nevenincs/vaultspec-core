---
tags:
  - '#exec'
  - '#adr-topic-infix'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S06'
related:
  - "[[2026-07-27-adr-topic-infix-plan]]"
---

# Cover MCP creation of topic-infixed ADRs in a mixed batch

## Scope

- `tests/unit/mcp_server/test_create_tool.py`

## Description

- Admit topic-infixed ADR specs in a mixed MCP create request.
- Retain the per-item failure for a topic-infixed plan spec.
- Assert the ADR file exists after the successful item completes.

## Outcome

MCP callers can create topic-infixed ADRs without losing mixed-batch isolation for
unsupported document types.

## Notes

`tests/unit/mcp_server/test_create_tool.py` passed: 9 tests.
