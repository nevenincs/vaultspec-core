---
tags:
  - '#exec'
  - '#mcp-tool-schema'
date: '2026-07-09'
modified: '2026-07-09'
step_id: 'S16'
related:
  - "[[2026-07-09-mcp-tool-schema-plan]]"
---

# Add the plan_edit tool: an operation list of add, insert, edit, and remove carrying the action-plus-scope shape, routed through the plan step verb logic that owns canonical identifiers and gap-no-reuse, against a resolver-addressed plan (agent: vaultspec-standard-executor)

## Scope

- `src/vaultspec_core/mcp_server/tools/plan.py`

## Description

- Add the `plan_edit` tool to the plan module: an operation list of add, insert, edit, and remove carrying the action-plus-scope shape, routed through the `add_step` / `insert_step` / `edit_step` / `remove_step` core that owns canonical identifiers and the gap-no-reuse rule.
- Apply operations sequentially against one parsed plan, fold a violated precondition (missing action, unknown anchor, unresolvable step) into a per-item failure rather than aborting the batch, and write once through the shared serialise-and-write helper.
- Keep phase and wave operations out of scope (gateway territory) and annotate the tool destructive and non-idempotent.

## Outcome

- Step-level plan authoring on the MCP surface with canonical-identifier and gap-no-reuse guarantees inherited from the owning verb logic, never hand-editing plan markdown.

## Notes

- No blockers.
