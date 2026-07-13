---
tags:
  - '#exec'
  - '#vault-orientation'
date: '2026-06-12'
modified: '2026-06-13'
step_id: S24
related:
  - '[[2026-06-12-vault-orientation-plan]]'
---

# add migration tests covering backfill, idempotence, and lenient date handling

## Scope

- `src/vaultspec_core/migrations/tests/test_m_0_1_29_modified_stamp_backfill.py`

## Description

- Add `src/vaultspec_core/migrations/tests/test_m_0_1_29_modified_stamp_backfill.py` with real on-disk fixtures, following the `test_index_subfolder` conventions; no mocks, patches, or skips.
- Cover backfill from `date:`, lenient-date canonicalization, the filename-prefix fallback when `date:` is unparseable, and multi-document backfill.
- Cover idempotence: an already-stamped document is byte-for-byte untouched, a non-canonical existing value is left for the checker (not normalized by the backfill), and a second run is a no-op.
- Cover the skip path: a document with no parseable `date:` and no filename prefix is skipped, and a filename date with no `date:` anchor is skipped rather than falsely counted as backfilled.
- Cover the no-vault no-op.
- Fix the wider-gate regressions surfaced by registering the checker: update the `vault check all` ordered-checker-name assertion to include `modified-stamp`; teach the index generator to emit a `modified:` stamp equal to `date:`; harden `_restamp_modified` in the repair pipeline and `_write_stamp` in the checker against case-only-rename stale paths via a case-sensitive parent-directory listing guard; update the lazy-migration-trigger test expectation to reflect the backfilled index.

## Outcome

The migration suite passes 10 tests; the wider gate over `vaultcore`, `migrations`, and `tests/cli` passes with `ty` clean across the package. The graph envelope contract was extended with the additive `modified` node field.

## Notes

Registering the checker into `run_all_checks` exposed a latent case-rename defect: a case-only filename rename leaves the old-cased relative path in the repair pipeline's changed-files set, and on a case-insensitive filesystem both `is_file` and `atomic_write` resolve it to the renamed file, resurrecting the original casing when the stamp writer touched it. A case-sensitive parent listing guard in both writers is the durable fix. The index generator gap (generated indexes lacked the schema-wide `modified:` field) is also corrected here so generated indexes reconcile cleanly.
