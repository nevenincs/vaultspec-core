---
tags:
  - '#exec'
  - '#mcp-tool-schema'
date: '2026-07-09'
modified: '2026-07-10'
step_id: 'S29'
related:
  - "[[2026-07-09-mcp-tool-schema-plan]]"
---

# Add the nine-tool integration test asserting registration of all nine tools, outputSchema presence, corrected annotations, and isError on a whole-call failure (agent: vaultspec-standard-executor)

## Scope

- `tests/unit/mcp_server/test_tool_surface.py`

## Description

- Add a WorkspaceFactory-based integration test that builds the real production server through `create_server` and drives it over the in-memory FastMCP session, with zero mocks, stubs, or skips.
- Assert the surface registers exactly the nine expected tool names and nothing more, each carrying an `outputSchema` and the ADR Q6 annotation matrix (read-only/idempotent for status/find/discover, non-idempotent create, destructive edit/plan_edit/invoke, idempotent plan_progress, non-read-only idempotent check).
- Assert the server instructions string names all nine tools and carries the tool-schema version.
- Exercise a representative call on every tool end-to-end: a create batch scaffolding a full research/adr/plan lifecycle, a plan_edit step add, a plan_progress close, an edit set_body through the shared engine, find in both modes, status rollup and trace, check, discover ranking, and a gateway invoke of the real `vault list` verb.
- Assert whole-call failures (empty create batch, unknown invoke verb) surface as protocol `isError`.
- Assert the shipped `.vaultspec/mcps/vaultspec-core.builtin.json` registry entry still launches this server module unchanged (ADR Q8), and that the launched module exposes the `create_server`/`run` bootstrap the test drives.

## Outcome

- New test: `tests/unit/mcp_server/test_tool_surface.py` (five tests, all passing).
- The nine-tool registration, annotation matrix, outputSchema presence, per-tool end-to-end behaviour, isError contract, and registry-launch invariance are now under a durable regression guard.

## Notes

- The representative-call test threads the created plan through plan_edit then plan_progress by capturing the returned canonical step id, so it makes no assumption about pre-existing template steps.
- The registry-launch assertion checks the builtin JSON args point at `vaultspec_core.mcp_server.app` and that the module exposes the same bootstrap, proving the sync-time no-op installation still serves the new surface.
