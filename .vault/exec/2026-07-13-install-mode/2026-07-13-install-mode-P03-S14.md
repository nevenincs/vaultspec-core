---
tags:
  - '#exec'
  - '#install-mode'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S14'
related:
  - "[[2026-07-13-install-mode-plan]]"
---

# Turn CANONICAL_ENTRY_PREFIX, the \_HOOK_DEFS entry values, CANONICAL_PRECOMMIT_HOOKS, and CANONICAL_HOOK_ENTRIES into functions of the resolved InstallMode, rendering uv run --no-sync vaultspec-core in dependency mode and uvx --from vaultspec-core vaultspec-core in tool mode

## Scope

- `src/vaultspec_core/core/commands.py`

## Description

- Replace the single hardcoded entry prefix with a mode-to-prefix table and `entry_prefix_for_mode`, mapping dependency mode to `uv run --no-sync vaultspec-core` and tool mode to `uvx --from vaultspec-core vaultspec-core`.
- Split the former hook definition map into mode-independent parts: a per-hook CLI subcommand map and a per-hook metadata map, both in the original scaffold order.
- Add `hook_defs_for_mode`, `canonical_precommit_hooks_for_mode`, and `canonical_hook_entries_for_mode`, each building the entry from the mode prefix and preserving the original field order so the scaffolded YAML is byte-stable.
- Keep `CANONICAL_ENTRY_PREFIX`, `CANONICAL_PRECOMMIT_HOOKS`, and `CANONICAL_HOOK_ENTRIES` as module-level names pinned to dependency mode so the doctor's canonical-entry check and any other importer stay byte-identical to today.

## Outcome

The hook prefix and the full canonical hook set are now functions of the provisioning mode while every pre-existing module-level constant keeps its exact prior value. A probe confirmed `canonical_precommit_hooks_for_mode(DEPENDENCY)` reproduces the previous `CANONICAL_PRECOMMIT_HOOKS` list field-for-field and key-order-for-key-order, and that tool mode renders the `uvx --from vaultspec-core vaultspec-core ...` entry for all four hooks. Because the module-level constants are unchanged, `collect_precommit_state` and the resolver continue to compare against the dependency-mode shape with no behavior change in this step; consuming the mode functions in the scaffolder is the next step.

## Notes

The original hook-field dict ordered `name`, `entry`, then the filter field (`types`/`always_run`); the new builder reproduces that order explicitly so the emitted `.pre-commit-config.yaml` does not churn. The `PrecommitHook` enum declaration order differs from the scaffold order, so the builder iterates the ordered metadata map rather than the enum to preserve the emitted hook sequence. The doctor's canonical-entry check keeping dependency-shaped expectations is a deliberate, documented handoff to the diagnosis phase, which makes that check derive its expected entries from the persisted mode.
