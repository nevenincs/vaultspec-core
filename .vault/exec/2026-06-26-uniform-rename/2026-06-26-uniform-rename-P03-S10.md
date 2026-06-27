---
tags:
  - '#exec'
  - '#uniform-rename'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S10'
related:
  - "[[2026-06-26-uniform-rename-plan]]"
---

# Add the cmd_feature_rename command with two positionals and dry-run, force, json, no-hints, and target options

## Scope

- `src/vaultspec_core/cli/vault_cmd.py`

## Description

- Added `cmd_feature_rename` registered under `@feature_app.command("rename")` with positional args `old_feature` and `new_feature`.
- Added `--dry-run`, `--force`, `--json`, `--no-hints`, and `--target` options matching the sibling `archive`/`unarchive` signature.
- Imported and called `rename_feature(root_dir, old, new, dry_run=dry_run, force=force)` from `vaultspec_core.vaultcore.query`.
- Caught `VaultSpecError` and `OSError` via `_handle_error` for consistent failure rendering.
- Invalidated the graph cache via `invalidate_graph_cache` on any successful non-dry-run apply.
- Added the `vault.feature.rename` hint entry to `_NEXT_STEP_HINTS` in `src/vaultspec_core/cli/rendering.py`.

## Outcome

All three quality gates pass: `ruff check`, `ruff format`, and `ty check` on `vault_cmd.py` emit no errors. Unit gate holds at 1377 passed.

## Notes

The `--force` flag wires through to the backend unchanged; per-file collision logic lives entirely in `rename_feature` and is not duplicated at the CLI layer.
