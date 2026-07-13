---
tags:
  - '#exec'
  - '#vault-orientation'
date: '2026-06-12'
modified: '2026-06-13'
step_id: S22
related:
  - '[[2026-06-12-vault-orientation-plan]]'
---

# add checker tests covering lenient parsing, normalization, and unparseable-value findings

## Scope

- `src/vaultspec_core/vaultcore/checks/tests/test_modified_stamp.py`

## Description

- Add `src/vaultspec_core/vaultcore/checks/tests/test_modified_stamp.py` with real on-disk fixtures built per test, following sibling checker test conventions; no mocks, patches, or skips.
- Drive every case through a real `VaultGraph.to_snapshot()` so the snapshot path that S21 fixed is exercised end to end.
- Cover the missing-stamp branch: flagged as a fixable warning; backfilled from `date:` under fix; backfilled from the filename prefix when `date:` is unparseable; left unfixed when no `date:` anchor exists.
- Cover the non-canonical branch: an ISO timestamp and a `yyyy/mm/dd` value are both flagged and normalized to the canonical quoted form, preserving the parsed value rather than today.
- Cover the unparseable branch: flagged as a non-fixable error that names the offending value, never rewritten, never dropped.
- Cover staleness: a document whose mtime date is newer than its stamp is flagged and, under fix, refreshed to the mtime date; mtimes are set with `os.utime`.
- Cover the clone-signature guard: a uniform-mtime vault suppresses all staleness findings and emits exactly one informational diagnostic, while a diverse-mtime vault below the 80 percent threshold runs staleness normally with no info diagnostic.
- Cover result shape: `check_name` is `modified-stamp`, `supports_fix` is true, a canonical fresh stamp is clean, and the feature filter scopes findings.

## Outcome

All 15 tests pass under `pytest -p no:randomly`; ruff and `ty` are clean. The suite distinguishes the clone guard from genuine staleness by spreading filler mtimes so the dominant date stays under threshold.

## Notes

Writing the staleness tests surfaced that the clone-signature guard trips when too many fixture documents share one mtime; the fixtures give fillers distinct mtime dates equal to their own stamps so they are neither stale nor a clone signature. The checker's date-last frontmatter insertion path (a `date:` line as the final frontmatter line) was hardened during this step and landed with `S21`.
