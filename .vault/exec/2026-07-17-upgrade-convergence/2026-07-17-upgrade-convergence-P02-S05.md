---
tags:
  - '#exec'
  - '#upgrade-convergence'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S05'
related:
  - "[[2026-07-17-upgrade-convergence-plan]]"
---

# Register the launch-shape convergence migration invoking mcp_sync per enrolled provider, idempotent against the refresh path

## Scope

- `src/vaultspec_core/migrations`

## Description

- Add the launch-convergence migration module registered for the next
  release: reads the project-scope ownership sidecar, reconciles exactly the
  providers with recorded vaultspec-managed enrollment through the owning
  mcp_sync verb, and reports refreshed/skipped/providers counts with a
  one-line operator summary.
- Register it in the migration registry build list.
- Dogfood on this workspace: six managed entries across three providers
  refreshed to the guarded shape on `migrations run`, registry reports
  applied, stdio handshake verified against the refreshed launch.

## Outcome

Every legacy workspace below the target version converges on its first
triggering verb (upgrade, any vault command, or migrations run) with no
flags; a workspace without recorded MCP enrollment is a true no-op.

## Notes

Sync warnings and errors are logged, never raised: a broken host file
reports through the sync surfaces without wedging the migration registry,
matching the registry doctrine of reserving failures for data-safety.
