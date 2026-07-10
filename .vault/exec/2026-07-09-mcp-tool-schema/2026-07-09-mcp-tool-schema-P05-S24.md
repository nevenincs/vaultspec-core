---
tags:
  - '#exec'
  - '#mcp-tool-schema'
date: '2026-07-09'
modified: '2026-07-09'
step_id: 'S24'
related:
  - "[[2026-07-09-mcp-tool-schema-plan]]"
---

# Migrate whole-call failures across every tool handler from the success-dict idiom to protocol isError, raising through FastMCP for invalid arguments, unknown verbs, and unresolvable targets while keeping per-item status only inside batch result arrays (agent: vaultspec-standard-executor)

## Scope

- `src/vaultspec_core/mcp_server/tools`

## Description

- Audit every tool handler across the nine-tool surface for the pre-structured-output success-dict idiom; confirm zero residual `{"success": false}` returns remain anywhere under `mcp_server`.
- Confirm each whole-call failure path already raises rather than returning a success-shaped dict: empty batch in `create` and `edit`, invalid `plan_progress` state, unresolvable plan address, unresolvable trace target in `status`, and unknown or denied verb in `invoke`; FastMCP surfaces each as protocol `isError`.
- Resolve the carried P03 flag: extract the two plan-write integrity guards (unexpected-retirement, issue #150, and growth-ceiling, issue #125) out of the Typer-coupled `_save_plan_or_dry_run` into a new shared `plan.write_guard` core returning through a `PlanWriteGuardError` that subclasses `PlanCommandError`.
- Re-point the CLI `_save_plan_or_dry_run` at the shared `guard_plan_write`, deleting the inline retirement and growth checks and the now-unused module constants.
- Wire the MCP `_save_plan` through the same guard and thread `expected_retired` from `plan_edit` (the batch's `remove` targets) so a serialisation conflict that would silently drop a live step now raises to `isError` instead of corrupting the plan.

## Outcome

- New shared core: `src/vaultspec_core/plan/write_guard.py` (`guard_plan_write`, `PlanWriteGuardError`).
- Re-pointed: `src/vaultspec_core/cli/plan_cmd.py` (guards now shared), `src/vaultspec_core/mcp_server/tools/plan.py` (`_save_plan` inherits the guards; `plan_edit` declares its expected retirements).
- The unexpected-retirement guard, which protects canonical-identifier and gap-no-reuse integrity, is now enforced identically on the CLI and MCP surfaces from one definition; the growth-ceiling guard travels with it.
- Existing CLI guard regression (`test_unexpected_retirement_check_direct`) passes unchanged against the shared implementation; the MCP plan-tool suite stays green.

## Notes

- The guard extraction is the chosen resolution of the P03 carried flag: the retirement guard is exactly the canonical-identifier protection the flag flagged, so shared extraction (not documented omission) was the correct disposition.
- No code change was required for the isError migration proper: earlier phases already routed whole-call failures through raises. This Step is the audit-and-confirm plus the guard hardening that closes the last whole-call integrity gap on the mutation surface.
