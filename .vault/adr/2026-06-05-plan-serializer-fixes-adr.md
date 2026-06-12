---
tags:
  - '#adr'
  - '#plan-serializer-fixes'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-06-05-plan-serializer-fixes-research]]'
---

# `plan-serializer-fixes` adr: `serializer-verification-and-obsolete-agents` | (**status:** `accepted`)

## Problem Statement

Two issues require structural fixes to prevent data loss in plan files and configuration conflicts:

1. Issue 150: During sequential plan mutations (adds/removes), visible phases or steps can be silently moved into the retired ledger comment block due to serializer constraints, parsing failures, or ordering conflicts.
1. Issue 149: Obsolesence of `.codex/agents/` individual TOML files and duplicate keys in `.codex/config.toml` outside the managed block cause config loading warnings and parser failures.

## Considerations

- Data loss in plan files must be prevented deterministically. Bypassing validation is not an option.
- The `_save_plan_or_dry_run` function handles all CLI write-backs, providing a single point of enforcement.
- Codex configuration has moved to a unified config TOML block inside `.codex/config.toml`, rendering the directory-based agent roles folder obsolete.
- Pruning obsolete files should be handled when `prune=True` is requested during `sync` or `install --upgrade`.

## Constraints

- We must not introduce new dependencies or libraries.
- The validation check must be fast and performant.
- `tomllib` standard library parser must be protected from crashes caused by duplicate keys.

## Implementation

1. **Serializer Verification (Issue 150)**:

   - Introduce a verification check in `_save_plan_or_dry_run` that parses the original plan text.
   - Compare the unioned set of retired IDs (`plan.retired_step_ids | plan.retired_phase_ids | plan.retired_wave_ids`) before and after the mutation.
   - Calculate `newly_retired = new_retired - old_retired`.
   - Pass an `expected_retired` set parameter from the CLI command handlers to `_save_plan_or_dry_run`.
   - If any `unexpected = newly_retired - expected` exists, raise `PlanCommandError` and abort the write operation.

1. **Obsolete Agents Pruning and Sanitization (Issue 149)**:

   - Implement directory and file deletion inside `_sync_codex_agents` when `prune=True`. If `.codex/agents/` exists, recursively delete files in it, and delete the directory itself if empty.
   - Refactor `_strip_agent_tables_in_segment` inside `src/vaultspec_core/core/agents.py` to match both `[agents.name]` tables and `name = ...` key assignments under `[agents]` tables that reside outside the managed comment blocks.

## Rationale

This design guarantees that any serializer or mutation bug that would silently retire visible plan rows is immediately caught and blocked. The file on disk remains completely untouched, preventing corruption. The Codex agents cleanup prevents duplicate configuration warnings and crashes in downstream IDE config loaders.

## Consequences

- CLI commands will fail fast and report an error if a bug or ordering constraint would silently retire active steps.
- Obsolete files and config tables are cleanly removed, ensuring config consistency.

## Codification candidates

- **Rule slug:** `mutation-verification`.
  **Rule:** Every plan mutation must verify that no unexpected identifiers are retired during the operation.
