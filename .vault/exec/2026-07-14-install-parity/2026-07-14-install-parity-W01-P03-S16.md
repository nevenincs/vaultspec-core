---
tags:
  - '#exec'
  - '#install-parity'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S16'
related:
  - "[[2026-07-14-install-parity-plan]]"
---

# Apply the render_mode aliasing helper in entry_prefix_for_mode and hook_defs_for_mode, and key \_scaffold_precommit's default resolution to resolve_render_mode(target, package='vaultspec-core')

## Scope

- `src/vaultspec_core/core/commands.py`

## Description

- Verify that `entry_prefix_for_mode` already routes its lookup through the
  shared render_mode helper (the P01 pull-forward) and that `hook_defs_for_mode`
  derives every hook entry from it, so both already collapse the `DEV` member
  onto the `DEPENDENCY` prefix without a third table branch; extend rather than
  redo.
- Key `_scaffold_precommit`'s default mode resolution explicitly to
  `resolve_render_mode(target, package='vaultspec-core')`, so core's hook
  scaffold reads core's own entry in the shared per-package map.

## Outcome

Hook rendering for `DEV` produces the same `uv run --no-sync vaultspec-core`
entries as `DEPENDENCY` and never raises; tool mode still renders the `uvx`
entries. The pre-commit scaffold now resolves its default mode from core's own
package entry. The migration-trigger and mode-flip suites (24 tests) pass and
`ty check` is clean.

## Notes

No code change was needed in `entry_prefix_for_mode` or `hook_defs_for_mode`:
the render_mode aliasing was already present from the P01 pull-forward and was
confirmed here, so this step only re-keys the default resolution.
