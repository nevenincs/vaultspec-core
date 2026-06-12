---
tags:
  - '#exec'
  - '#vault-orientation'
date: '2026-06-12'
modified: '2026-06-12'
step_id: S20
related:
  - '[[2026-06-12-vault-orientation-plan]]'
---

# add a checker that flags missing, unparseable, or stale modified stamps and normalizes parsed values to canonical form under fix

## Scope

- `src/vaultspec_core/vaultcore/checks/modified_stamp.py`

## Description

- Add `check_modified_stamp` to `src/vaultspec_core/vaultcore/checks/modified_stamp.py`, mirroring the snapshot-plus-fix contract of `frontmatter.py`.
- Reuse `parse_lenient_date` and `normalize_date` from `models` for all date handling; do not reimplement parsing.
- Flag a missing `modified:` field; under fix, add it from the lenient-parsed `date:`, falling back to the filename `yyyy-mm-dd` prefix when `date:` is absent or unparseable.
- Flag a present-but-non-canonical yet parseable stamp; under fix, rewrite to the canonical quoted `yyyy-mm-dd` of the parsed value, never today.
- Flag an unparseable stamp as an error, naming the offending value; never auto-fix and never drop it.
- Flag a stale stamp (file mtime date strictly newer than the stamp); under fix, refresh to the mtime date.
- Guard staleness against the fresh-clone signature: when 80 percent or more of in-scope documents share one mtime date, suppress all staleness findings and emit one informational diagnostic; documented in the module docstring.
- Add a local `_write_stamp` helper that preserves the source CRLF/LF convention and writes atomically with a `.bak` rollback, mirroring `_fix_frontmatter`.

## Outcome

The `modified-stamp` checker exists with full D3b semantics and the clone-signature guard. Ruff format, ruff check, and `ty` all pass on the new module. Registration and live verification follow in `S21`.

## Notes

The staleness branch reads file mtime directly via `Path.stat`; the missing, non-canonical, and unparseable branches read only frontmatter and are unaffected by the clone-signature guard.
