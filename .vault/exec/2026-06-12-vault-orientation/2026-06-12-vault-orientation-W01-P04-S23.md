---
tags:
  - '#exec'
  - '#vault-orientation'
date: '2026-06-12'
modified: '2026-06-13'
step_id: S23
related:
  - '[[2026-06-12-vault-orientation-plan]]'
---

# add a schema migration backfilling modified from date across existing vault documents

## Scope

- `src/vaultspec_core/migrations/m_0_1_29_modified_stamp_backfill.py`

## Description

- Add `src/vaultspec_core/migrations/m_0_1_29_modified_stamp_backfill.py` targeting version `0.1.29`, following the `m_0_1_17_index_subfolder` contract (target version, applies-to detection via docs-dir walk, idempotence, `MigrationError` on I/O failure).
- Walk `<workspace>/<docs_dir>/` for every `*.md`; for each document lacking a `modified:` field, insert a canonical stamp from the lenient-parsed `date:`, falling back to the filename `yyyy-mm-dd` prefix, else skip with a recorded reason.
- Leave documents that already carry the field byte-for-byte untouched so a second run is a true no-op.
- Reuse `normalize_date` plus the checker's `_write_stamp` and `_filename_date` so insertion preserves the source newline convention and the canonical schema position; no date logic is reimplemented.
- Report `backfilled`, `already`, and `skipped` counts in the `MigrationResult`.
- Register the migration in the `migrations` `__init__.py` registry, appended in version order after `codex_agents_dedup`.

## Outcome

Ruff and `ty` are clean. The migration is registered and discovered by the driver. Behaviour is covered by `S24`; the live vault was already seeded by the `S21` reconciliation pass, so a run here reports every document under `already` (the idempotent no-op path).

## Notes

The backfill deliberately does not normalize or refresh an existing `modified:` value; that is the reconciliation checker's responsibility. A document with neither a parseable `date:` nor a filename date prefix, or with no `date:` anchor to insert after, is skipped rather than stamped with an invented date.
