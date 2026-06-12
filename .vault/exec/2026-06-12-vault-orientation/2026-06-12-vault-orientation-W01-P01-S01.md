---
tags:
  - '#exec'
  - '#vault-orientation'
date: '2026-06-12'
modified: '2026-06-12'
step_id: S01
related:
  - '[[2026-06-12-vault-orientation-plan]]'
---

# add the modified field with lenient multi-format date parsing and canonical-form validation to DocumentMetadata

## Scope

- `src/vaultspec_core/vaultcore/models.py`

## Description

- Add `parse_lenient_date` to `src/vaultspec_core/vaultcore/models.py` as the single canonical lenient-date helper (ADR D3b): accepts date and datetime objects, canonical yyyy-mm-dd, ISO timestamps with optional zone, yyyy/mm/dd, and year-last dd-mm-yyyy or mm/dd/yyyy only when one component exceeds 12; rejects ambiguous values instead of guessing
- Add `normalize_date` returning the canonical yyyy-mm-dd string or None, for reuse by the later checker, migration, and status phases
- Add the `modified` field to `DocumentMetadata` alongside `date`, documented as the CLI-maintained recency stamp
- Extend `DocumentMetadata.validate` with the lenient policy: canonical modified is valid, lenient-parseable noncanonical is accepted (the check-fix path normalizes it later), unparseable values produce a violation
- Re-export `parse_lenient_date` and `normalize_date` from the `vaultcore` package init for downstream consumers

## Outcome

The document model carries the `modified` stamp with a reusable lenient parsing API. All 208 vaultcore tests pass; ruff format, ruff check, and ty check are clean.

## Notes

The frontmatter check-fix renderer in `src/vaultspec_core/vaultcore/checks/frontmatter.py` preserves unknown keys, so it does not reject `modified`; its explicit known-keys handling lands in S02 (parser scope) where the parsed value becomes available for rendering.
