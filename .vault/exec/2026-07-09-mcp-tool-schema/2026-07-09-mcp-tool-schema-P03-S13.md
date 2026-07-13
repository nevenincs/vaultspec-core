---
tags:
  - '#exec'
  - '#mcp-tool-schema'
date: '2026-07-09'
modified: '2026-07-10'
step_id: 'S13'
related:
  - "[[2026-07-09-mcp-tool-schema-plan]]"
---

# Add the status tool over vaultcore.orientation: compute_rollup for the unparameterized orientation view and compute_trace for a feature-or-plan target, returning the feature inventory, in-flight plans with tier and completion, next open step, and the tool-schema package version as structured content (agent: vaultspec-standard-executor)

## Scope

- `src/vaultspec_core/mcp_server/tools/orientation.py`

## Description

- Add the orientation tool module with a `status` tool that wraps `compute_rollup` for the unparameterized project view and `compute_trace` for a feature-or-plan target.
- Return a typed `StatusResult` carrying the active-feature inventory with lifecycle status, the plans in flight with tier and completion and next open step, the vault totals, and the tool-schema package version, plus the per-plan grounding trace for a target.
- Return no blob hashes, keeping the read-then-edit chain sourced from `find`; convert an unresolvable trace target into a whole-call protocol error.
- Annotate the tool read-only and idempotent.

## Outcome

- A thin, read-only orientation tool over the orientation core that surfaces the project rollup and the targeted grounding trace with the schema version echoed for the stateless protocol.

## Notes

- No blockers.
