---
tags:
  - '#exec'
  - '#uniform-rename'
date: '2026-06-26'
modified: '2026-06-27'
step_id: 'S12'
related:
  - "[[2026-06-26-uniform-rename-plan]]"
---

# Emit the versioned json envelope vaultspec.vault.feature.rename.v1 with canonical status

## Scope

- `src/vaultspec_core/cli/vault_cmd.py`

## Description

- Emitted the JSON envelope via `json_envelope("vault.feature.rename", rename_status, result, hints=hint_dict)` using the same `json_envelope` helper used by every sibling command.
- Chose `rename_status` as `"updated"` when `renamed_count > 0` and not a dry-run, otherwise `"unchanged"`.
- Failure path uses `_handle_error` which emits `vaultspec.error.v1` with `"failed"` status and a `"message"` payload, consistent with archive and unarchive.
- Schema string resolves to `vaultspec.vault.feature.rename.v1` (default version=1 from `json_envelope`).

## Outcome

Smoke test JSON envelopes confirmed:

- Dry-run: `schema=vaultspec.vault.feature.rename.v1`, `status=unchanged`, payload carries `dry_run=true` and predicted counts.
- Real rename: same schema, `status=updated`, payload carries `renamed_count`, `paths`, `exec_folders`, `tag_rewrites`, `related_rewrites`, `link_renames`, `index`, `cross_links`, `collisions`.
- Collision case (no --force): `schema=vaultspec.error.v1`, `status=failed`, non-zero exit.

## Notes

No new envelope format was invented. The `json_envelope` utility and the `_handle_error` failure path are identical call sites to `cmd_feature_archive`, ensuring the rename command fits the existing consumer contract without any schema drift.
