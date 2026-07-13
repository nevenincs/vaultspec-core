---
tags:
  - '#exec'
  - '#mcp-tool-schema'
date: '2026-07-09'
modified: '2026-07-10'
step_id: 'S09'
related:
  - "[[2026-07-09-mcp-tool-schema-plan]]"
---

# Add WorkspaceFactory tests for batch create: intra-batch lifecycle dependency validation, per-item partial-failure envelope, and automatic feature-index regeneration for affected features (agent: vaultspec-standard-executor)

## Scope

- `tests/unit/mcp_server/test_create_tool.py`

## Description

- Add a WorkspaceFactory conftest that installs a real vault over a stdlib tempfile root, sets the global path context, and unwraps a tool result into its structured payload.
- Add the batch create tests driving the real FastMCP server over the in-memory session transport with zero mocks.
- Cover the intra-batch lifecycle dependency: research, ADR, plan, and exec scaffold in one call, with exec satisfied by the earlier same-batch items.
- Cover the partial-failure envelope: an exec before its plan fails per item while the item after it still applies and the aggregate is mixed.
- Cover the automatic feature-index regeneration side effect, the per-item index-type rejection, the empty-batch protocol error, and seed-content append.

## Outcome

- Six create tests pass on the real filesystem, proving intra-batch dependency, partial-failure semantics, and index regeneration with no test doubles.

## Notes

- The tests sidestep the repo tmp_path compat shim in favor of a stdlib tempfile root per the plan constraint; the old flat-shape create tests in the tests/mcp suite were removed since create now takes a document list.
