---
tags:
  - '#exec'
  - '#mcp-tool-schema'
date: '2026-07-09'
modified: '2026-07-09'
step_id: 'S25'
related:
  - "[[2026-07-09-mcp-tool-schema-plan]]"
---

# Declare outputSchema and return structuredContent via FastMCP return-type derivation on all nine tools, replacing loose dict returns with typed result models (agent: vaultspec-standard-executor)

## Scope

- `src/vaultspec_core/mcp_server/tools`

## Description

- Audit every tool's return type for structured-output derivation: build the real server and enumerate each registered tool's `outputSchema`.
- Confirm all seven hot tools already return typed Pydantic models rather than loose dicts or lists: `find` returns a `FindEntry` list, `create` and `edit` return `BatchResult`, `status` returns `StatusResult`, `check` returns `CheckResultModel`, `plan_progress` returns `PlanProgressResult`, `plan_edit` returns `PlanEditResult`.
- Confirm the two gateway tools return `DiscoverResult` and `InvokeResult`, so all nine derive an `outputSchema` and return `structuredContent` through FastMCP return-type derivation.

## Outcome

- Probe against `create_server` reports `outputSchema` present on every registered tool (seven at this point; the gateway pair is wired in the following Step and re-verified end-to-end by the surface integration test).
- No loose-dict or bare-list return remains on the surface; no code change was required because the prior phases authored each tool over a typed result model from the start.

## Notes

- This Step is an audit-and-confirm: the structured-output contract was satisfied incrementally as each tool landed, so the closeout obligation is verification rather than remediation. The nine-tool assertion is proven end-to-end by the surface integration test added later in the Phase.
