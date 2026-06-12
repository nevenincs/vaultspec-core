---
tags:
  - '#exec'
  - '#vault-orientation'
date: '2026-06-12'
modified: '2026-06-12'
step_id: S15
related:
  - '[[2026-06-12-vault-orientation-plan]]'
---

# refresh both documents' modified stamps during adr supersession

## Scope

- `src/vaultspec_core/core/adr.py`

## Description

- Import the shared `refresh_modified_stamp` helper and `datetime` into `src/vaultspec_core/core/adr.py`.
- In `adr_supersede`, refresh the modified stamp on both rendered documents (the superseded old ADR and the superseding new ADR) immediately before the writes, applied to the final CRLF-reapplied text so the helper rewrites the exact bytes about to be written and preserves each document's line-ending convention.

## Outcome

`vault adr supersede` now stamps both the old and the new ADR with today's date, treating supersession as the lifecycle mutation it is per decision D3. Because the function rebuilds frontmatter line by line without emitting `modified:` in its known-key pass, the helper is what establishes or refreshes the field: a pre-existing stamp (carried through the unknown-key passthrough) is rewritten to today, and a stamp-less ADR gains the field after `date:`. A dry-run still writes nothing. Targeted suites pass; ruff and ty clean.

## Notes

The stamp refresh runs unconditionally on the rendered text, but the actual disk write remains guarded by the existing `dry_run` check, so a preview run leaves both files untouched.
