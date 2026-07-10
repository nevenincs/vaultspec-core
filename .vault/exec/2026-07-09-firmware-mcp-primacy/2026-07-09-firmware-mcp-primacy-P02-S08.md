---
tags:
  - '#exec'
  - '#firmware-mcp-primacy'
date: '2026-07-09'
modified: '2026-07-09'
step_id: 'S08'
related:
  - "[[2026-07-09-firmware-mcp-primacy-plan]]"
---

# Read the reworded system prompt file through in both the MCP-connected and disconnected readings and confirm the Q4 after-form is verbatim, the subagent clause is present, and no availability conditional was introduced

## Scope

- `src/vaultspec_core/builtins/system/03-vaultspec.md`

## Description

- Read the reworded system prompt through in the MCP-connected reading: status, plan_progress, and plan_edit are named primary at the orchestrator surface.
- Read it through in the disconnected reading: every named tool has a CLI path in the same sentence or clause.
- Confirm the plan-verbs paragraph matches the ADR Q4 after-form verbatim.
- Confirm the subagent clause is present in the Agents section.
- Confirm no availability conditional was introduced.

## Outcome

- The system prompt passes the two-world read-through: Q4 after-form verbatim, subagent clause present, both readings correct, no availability conditional.

## Notes

- This read-through is the Phase P02 verification; the mandatory closeout code review remains scoped to P05.
