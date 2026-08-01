---
tags:
  - '#audit'
  - '#mcp-read-only'
date: '2026-08-01'
modified: '2026-08-01'
body_schema: 'body-v1'
body_hash: 'sha256:c5ef76e30166d38477bd03fc5295cbfdb77a0be58f0b7f89b374408580305ca3'
related:
  - '[[2026-08-01-mcp-read-only-research]]'
  - '[[2026-08-01-mcp-read-only-adr]]'
  - '[[2026-08-01-mcp-read-only-plan]]'
---
# `mcp-read-only` audit: `read-only MCP launch mode`

## Scope

Reviewed issue #300 against the accepted research, ADR, and L1 plan: launch parsing, server registration, `check` schemas and behavior, normal-mode compatibility, and the in-memory and stdio MCP tests. The final focused MCP suite passed: 8 tests.

## Findings

### forbidden-fix-argument | medium | Restricted `check` silently accepts `fix`

A real `create_server(read_only=True)` session initially accepted `check` with `{"fix": true}` as a successful call. The handler ran with `fix=False`, so it did not repair, but the restricted interface neither rejected the prohibited argument nor proved that clients could not rely on it. This violated the ADR constraint that restricted `check` must neither advertise nor accept `fix`.

### normal-repair-regression-guard | low | Default repair compatibility lacked behavioral coverage

The normal catalog initially retained `check` with `fix`, but its tests asserted only tool names, annotations, and a no-argument validation call. They did not execute `check` with `{"fix": true}`.

## Recommendations

- Keep explicit wire-level rejection for prohibited read-only `check` arguments as the SDK evolves.
- Retain normal-mode `fix` coverage whenever the check tool is changed.

## Resolution

The medium finding is resolved by a read-only MCP extension guard that returns an error result when a `check` request includes `fix`. In-memory and real stdio sessions now prove the schema omits `fix` and a supplied `fix` is rejected. The default-surface test now proves that `fix` remains advertised and a real normal-mode `check` call accepts `fix=True` and reports that repair mode was applied.
