---
tags:
  - '#exec'
  - '#mcp-tool-schema'
date: '2026-07-09'
modified: '2026-07-10'
step_id: 'S15'
related:
  - "[[2026-07-09-mcp-tool-schema-plan]]"
---

# Add the plan_progress tool: mark a batch of canonical step ids checked or unchecked (explicit states only, no toggle) via plan.commands.step_ops against a plan resolved by the shared resolver, returning updated completion counts and the next open step (agent: vaultspec-standard-executor)

## Scope

- `src/vaultspec_core/mcp_server/tools/plan.py`

## Description

- Add the plan tool module with a `plan_progress` tool that resolves a plan by feature or stem through the shared resolver and marks a batch of canonical step ids checked or unchecked over the `check_step` / `uncheck_step` core.
- Accept explicit states only (no toggle) so the tool is idempotent; report each item as updated, unchanged, or failed, and let an unresolvable step id fail per item without aborting the batch.
- Add a shared load/serialise/write helper mirroring the CLI plan-mutation path (parse, mutate, serialise with unknown blocks preserved, refresh the modified stamp, atomic-write only when the bytes changed), and write once at the end of the batch.
- Return the post-batch completion counts and next open step via `collect_status`.

## Outcome

- The highest-frequency corpus operation is on the MCP surface as an idempotent, thin wrapper over the plan step-ops core, returning updated completion and the next open step.

## Notes

- No blockers.
