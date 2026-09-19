---
tags:
  - '#exec'
  - '#mcp-tool-schema'
date: '2026-09-19'
modified: '2026-09-19'
body_schema: 'body-v2'
body_hash: 'sha256:4e86e6883b735fe406e1ec014c59e12064575d8f462146f4243bc465d7328ecb'
related:
  - "[[2026-09-19-mcp-tool-schema-plan]]"
---

# `mcp-tool-schema` ledger

## Changes

- `S01` `M` `src/vaultspec_core/mcp_server/app.py`
- `S01` `M` `src/vaultspec_core/mcp_server/tests/test_tool_surface.py`
- `S01` `verify:` `pytest src/vaultspec_core/mcp_server/tests/test_tool_surface.py` -> `pass`
- `S03` `M` `pyproject.toml`
- `S03` `M` `uv.lock`
- `S03` `verify:` `just audit-dependencies` -> `pass`
- `S06` `M` `src/vaultspec_core/mcp_server/tools/documents.py`
- `S06` `M` `docs/MCP.md`
- `S06` `verify:` `pytest src/vaultspec_core/mcp_server/tests/test_find_tool.py test_find_queries.py` -> `pass`
- `S07` `M` `docs/channels.md`
- `S07` `verify:` `just check-markdown` -> `pass`
- `S02` `M` `src/vaultspec_core/mcp_server/tools/gateway.py`
- `S02` `M` `src/vaultspec_core/mcp_server/tests/test_gateway.py`
- `S02` `verify:` `pytest src/vaultspec_core/mcp_server/tests` -> `pass`
- `S02` `by:` `opus executor`

## Notes

- `S01` The prior guard asserted a bare substring, which 'log' satisfied via 'catalog', so the ledger tool was absent from the orientation string while the check reported green. The regression was reproduced against the restored string before the fix was accepted.
- `S03` The deptry ignore block posed the removal as blocked on an unanswered intent question: whether the three floors were security pins. Resolved by evidence rather than assumption - the floors trace to the A2A rewrite commit whose ADRs, plan and code no longer exist, the OSV gate reports no advisory against any of the three, and the SDK requires all three transitively, so the resolved versions are unchanged. The ignore entries were removed with the declarations rather than left standing.
- `S06` The description called resource_uri a resource-link, which is the ambiguity the audit recorded: it is a file locator, not a protocol resource_link, and no resource is registered for it. Step left open until the generated tool inventory is regenerated, which is deferred while the gateway module is under edit by the cancellation Step.
- `S07` The note states no version number: release-please chooses the bump and a public entry-point rename could land as either a minor or a patch, so asserting one would be a claim this change does not control.
- `S02` The explicit reap is load-bearing, not defensive. anyio's process context exit kills only when its internal wait is itself interrupted; here the process manager wraps the timeout scope rather than sitting inside it, so removing the reap makes a cancelled or timed-out verb hang for the child's full natural lifetime. Measured at 60s on both paths by deleting the call and re-running.
- `S02` The first probe of this behaviour reported the opposite because it measured liveness only after the context manager returned, which a 60s wait-out satisfies. The tests carry a wall-clock bound for the same reason: without it they cannot distinguish a killed child from an outlived one.
- `S02` The end-to-end cancellation test depends on a private SDK module for raw request-id control, and its unanswered-request assertion does not discriminate this code because the SDK discards a cancelled id's response regardless. The child's death is the discriminating assertion; the docstring was corrected to say so rather than claim otherwise.
