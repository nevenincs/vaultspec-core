---
tags:
  - '#exec'
  - '#provider-mcp-enrollment'
date: '2026-07-15'
modified: '2026-07-15'
step_id: 'S03'
related:
  - "[[2026-07-15-provider-mcp-enrollment-plan]]"
---

# Implement Claude JSON and Codex TOML reconciliation, status, prune, and uninstall

## Scope

- `src/vaultspec_core/core/mcps.py`

## Description

- Reconcile canonical stdio definitions into Claude project, local, and user JSON stores plus Codex project and user TOML stores.
- Preserve unrelated Codex settings and comments through a comment-bounded managed block and surgical force adoption.
- Move ownership names and observed fingerprints into external project or user state.
- Migrate only affirmative legacy ownership and remove the unsupported host-schema marker.
- Aggregate missing, drifted, stale, and external entries independently per provider.
- Prune and uninstall only recorded managed entries with per-provider `SyncResult` outcomes.
- Bootstrap explicit `target_dir` and `enrolled` calls without relying on ambient workspace context.

## Outcome

Real-file probes passed fresh native writes, idempotence, same-name collision preservation and explicit adoption, unrelated TOML byte preservation, affirmative legacy migration, conservative no-marker migration, source-safe prune, independent provider drift, provider-scoped uninstall, explicit Claude local scope, and standalone sync/status/uninstall without a preinitialized context. Ruff and type checks pass. A real fresh installation wrote Claude, Antigravity, and Codex project targets; Claude CLI recognized its project entry, while Codex correctly withheld the untrusted temporary project configuration.

## Notes

The existing JSON-only tests intentionally remain for the dedicated test-replacement step. Codex host acceptance must create an isolated trusted project in the dedicated acceptance step rather than weakening the host trust boundary.
