---
tags:
  - '#exec'
  - '#mcp-tool-schema'
date: '2026-07-09'
modified: '2026-07-09'
step_id: 'S14'
related:
  - "[[2026-07-09-mcp-tool-schema-plan]]"
---

# Add the check tool over vaultcore.checks: run the check suite with an optional fix flag and return structured findings, annotated read-only without fix and non-read-only idempotent with fix (agent: vaultspec-low-executor)

## Scope

- `src/vaultspec_core/mcp_server/tools/orientation.py`

## Description

- Add the `check` tool to the orientation module as a thin wrapper over the `run_all_checks` suite core, with an optional `fix` flag and an optional feature filter.
- Fold the per-checker results into a typed `CheckResultModel`: per-checker summary lines, the flattened error- and warning-severity findings, aggregate counts, the applied-fix flag, and an aggregate ok/failed status.
- Annotate the tool non-read-only, non-destructive, and idempotent per the ADR, since it can repair yet converges on re-run and never overwrites authored prose.

## Outcome

- Vault validation and repair on the MCP surface, returning structured findings that mirror the CLI check suite.

## Notes

- No blockers.
