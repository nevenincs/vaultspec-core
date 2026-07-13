---
tags:
  - '#exec'
  - '#vault-orientation'
date: '2026-06-12'
modified: '2026-06-13'
step_id: S02
related:
  - '[[2026-06-12-vault-orientation-plan]]'
---

# parse and surface the modified frontmatter field through typed metadata parsing

## Scope

- `src/vaultspec_core/vaultcore/parser.py`

## Description

- Parse the `modified` frontmatter scalar in `parse_vault_metadata` in `src/vaultspec_core/vaultcore/parser.py`, stripping quotes and coercing empty values to None, mirroring the `archived` handling
- Add `modified` to the check-fix renderer's known keys in `src/vaultspec_core/vaultcore/checks/frontmatter.py` so the rebuild path renders it explicitly (quoted, after `date`) instead of via the unknown-key passthrough

## Outcome

The typed metadata path surfaces `modified` end to end: parse, validate, and check-fix rebuild. All 208 vaultcore tests pass; ruff format, ruff check, and ty check are clean.

## Notes

The check-fix renderer change was assigned to S01/S02 scope by the plan brief; it landed here because the renderer reads `metadata.modified`, which only the parser populates.
