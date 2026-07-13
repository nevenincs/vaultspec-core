---
tags:
  - '#exec'
  - '#mcp-tool-schema'
date: '2026-07-09'
modified: '2026-07-10'
step_id: 'S20'
related:
  - "[[2026-07-09-mcp-tool-schema-plan]]"
---

# Add the discover tool: rank the parsed catalog over a query across verb paths and descriptions and return the ranked verb paths with their full parameter schemas, loaded into context only on demand, annotated read-only and idempotent (agent: vaultspec-standard-executor)

## Scope

- `src/vaultspec_core/mcp_server/tools/gateway.py`

## Description

- Add the gateway tools module and the `discover` tool as a thin, read-only query over the shared catalog, resolving the CLI reference path from the active workspace context (the parent of the templates directory) rather than any hardcoded location.
- Build and memoize the catalog per resolved reference path so the parse and Typer introspection run once and are reused across calls.
- Return ranked verb paths with their full parameter schemas and descriptions through typed Pydantic output models, so a verb's schema enters context only when the agent fetches it; the static denylist is already applied so denied verbs never surface.
- Annotate the tool read-only, idempotent, non-open-world, and wrap the handler in the shared copied-context isolation wrapper.

## Outcome

- `discover` ranks a known verb to the top for a plausible intent query, returns non-increasing scores, carries each verb's flag schema and `--json` support, and excludes denylisted verbs.

## Notes

- P04 deliberately does not wire the gateway into `create_server`; that bootstrap and instructions-string edit is the P05 closeout, so the tests register the handlers onto a local server to exercise them end to end.
