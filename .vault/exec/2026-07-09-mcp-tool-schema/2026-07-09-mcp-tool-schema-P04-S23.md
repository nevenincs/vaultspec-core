---
tags:
  - '#exec'
  - '#mcp-tool-schema'
date: '2026-07-09'
modified: '2026-07-10'
step_id: 'S23'
related:
  - "[[2026-07-09-mcp-tool-schema-plan]]"
---

# Add tests for the gateway executor against the real uv run --no-sync vaultspec-core binary, covering a read-only verb returning parsed JSON, an unknown verb path rejected before spawn, a nonzero exit folding stderr into the error payload, and the discover ranking order (agent: vaultspec-standard-executor)

## Scope

- `tests/unit/mcp_server/test_gateway.py`

## Description

- Add the gateway test module driving `discover` and `invoke` over the in-memory FastMCP session against a WorkspaceFactory-installed vault, with `invoke` spawning the real module entry as an argv-list subprocess and no mocks, stubs, or skips.
- Assert a read-only `--json` verb returns parsed structured data (the real `vault list` envelope) with the interpreter-free command preview, an unknown verb and each denylisted verb are rejected as protocol errors before any spawn, and a missing-positional verb folds its stderr and exit code into the structured error payload while remaining a successful call.
- Assert reserved and undeclared flags are refused before spawn, a declared value flag reaches the binary as a discrete argv item, and `discover` returns non-increasing ranked schemas that include a known verb and exclude denylisted verbs.

## Outcome

- Nine gateway tests pass against the real worktree binary, proving the parsed-JSON path, the pre-spawn rejection guards, the stderr-folding error path, and the discover ranking order.

## Notes

- The gateway is registered onto a local FastMCP instance in the test rather than through `create_server`, because wiring the gateway into the server bootstrap is the P05 closeout step.
