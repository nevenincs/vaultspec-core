---
tags:
  - '#exec'
  - '#mcp-static-launch'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S07'
related:
  - "[[2026-07-17-mcp-static-launch-plan]]"
---

# Document the static-execution launch contract and refresh rendered-launch examples in the MCP doc and the CLI reference builtins source

## Scope

- `docs/MCP.md`

## Description

- State the static-execution launch contract in the MCP doc install-modes
  section: a client connect never installs, resolves, or repairs; broken
  environments fail honestly; repair is an explicit dev action; pre-guard
  bare launches surface as doctor drift with the sync --force / install
  --upgrade remediation.
- Update the dependency and development mode launch descriptions to the
  guarded uv run --no-sync shape.
- Update the module-invocation entry-point examples in the CLI doc and the
  CLI reference builtins source, then roll the mirror with install
  --upgrade.

## Outcome

User documentation now states the contract the renderer enforces; no doc or
reference example shows the un-guarded launch shape.

## Notes

None.
