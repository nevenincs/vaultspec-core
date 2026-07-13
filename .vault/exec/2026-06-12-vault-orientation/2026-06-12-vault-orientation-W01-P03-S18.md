---
tags:
  - '#exec'
  - '#vault-orientation'
date: '2026-06-12'
modified: '2026-06-13'
step_id: S18
related:
  - '[[2026-06-12-vault-orientation-plan]]'
---

# refresh modified stamps on repair-pipeline document rewrites

## Scope

- `src/vaultspec_core/vaultcore/repair.py`

## Description

- Add a `_restamp_modified` helper to `src/vaultspec_core/vaultcore/repair.py` that, given the set of relative paths the fix phase changed, reloads each existing markdown document, refreshes its modified stamp via the shared helper, and rewrites it only when the stamp differs. Renamed, deleted, and non-markdown paths are skipped, and the line-ending convention is preserved.
- Call `_restamp_modified` in `run_repair_pipeline` right after the FIX phase records its file deltas, scoped to exactly the files the fix changed (computed from the pre-fix and post-fix fingerprints), and re-fingerprint afterwards so the index and postcheck phases observe the restamped state rather than reporting the stamp write as fresh drift. The restamp is gated on `not dry_run` so a preview run rewrites nothing.

## Outcome

`vault repair` (and the `vault check all --fix` surface it wraps) now refreshes the modified stamp on exactly the documents its fix pass rewrote, leaving every untouched document byte-for-byte intact. The scoping uses the pipeline's existing fingerprint deltas, so no extra vault scan is introduced, and the post-restamp re-fingerprint keeps the journal and postcheck phases honest. Targeted suites pass; ruff and ty clean.

## Notes

The repair module itself never wrote documents before; the writes live inside the individual checkers. Rather than thread the stamp through every checker, the restamp is applied once at the pipeline level over the precise set of changed files, which keeps the discipline in one place and matches the ADR's "only documents the repair actually rewrites" scoping.
