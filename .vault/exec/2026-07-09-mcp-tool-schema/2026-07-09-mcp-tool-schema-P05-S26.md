---
tags:
  - '#exec'
  - '#mcp-tool-schema'
date: '2026-07-09'
modified: '2026-07-09'
step_id: 'S26'
related:
  - "[[2026-07-09-mcp-tool-schema-plan]]"
---




# Correct the ToolAnnotations per ADR Q6: fix create's wrong idempotent hint to non-idempotent, mark edit and plan_edit and invoke destructive, keep plan_progress idempotent with explicit checked/unchecked only, and set status/find/discover read-only idempotent (agent: vaultspec-low-executor)

## Scope

- `src/vaultspec_core/mcp_server/tools`

## Description

- Audit every tool's `ToolAnnotations` against ADR Q6 by enumerating the registered tools' annotation hints on the real server.
- Confirm `status`, `find`, and `discover` are read-only and idempotent with `openWorldHint` false.
- Confirm `create` carries the corrected non-idempotent hint (`readOnlyHint` false, `destructiveHint` false, `idempotentHint` false), replacing the old wrong idempotent hint.
- Confirm `edit`, `plan_edit`, and `invoke` are destructive; `plan_progress` is idempotent with explicit `checked`/`unchecked` states and no toggle; `check` is non-read-only, non-destructive, idempotent (it loses read-only only because of the optional `fix`).

## Outcome

- Probe against `create_server` reports the exact annotation matrix ADR Q6 specifies for every registered tool; the gateway `discover` (read-only, idempotent) and `invoke` (destructive) annotations are confirmed at their registration site.
- No code change was required: the prior phases set each annotation to the ADR-mandated value when the tool landed, including the create idempotent-hint correction.

## Notes

- This Step is an audit-and-confirm; the annotation matrix is asserted end-to-end by the surface integration test added later in the Phase, so the closeout leaves a durable regression guard rather than only a point-in-time check.
