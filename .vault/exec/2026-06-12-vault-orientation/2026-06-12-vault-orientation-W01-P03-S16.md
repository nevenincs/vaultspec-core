---
tags:
  - '#exec'
  - '#vault-orientation'
date: '2026-06-12'
modified: '2026-06-13'
step_id: S16
related:
  - '[[2026-06-12-vault-orientation-plan]]'
---

# refresh the source audit's modified stamp on rule promotion

## Scope

- `src/vaultspec_core/core/rules.py`

## Description

- Inspect `rule_promote` to confirm it mutates the source audit: it appends a `rule:<name>` reference to the audit's `promoted_to` frontmatter list, rebuilds the audit frontmatter, and writes the audit back via `atomic_write`. The promote path therefore does rewrite the audit, so a stamp refresh is warranted.
- Import the shared `refresh_modified_stamp` helper and `datetime` into `rule_promote`, alongside the existing inline imports.
- Refresh the modified stamp on the rebuilt audit content immediately before the writes, applied to the final newline-normalized text so the document's line-ending convention is preserved.

## Outcome

`vault rule promote` now refreshes the source audit's modified stamp to today, because the verb genuinely mutates that audit's frontmatter (the `promoted_to` append). The freshly scaffolded rule file carries its own scaffold-time stamp and is not restamped here. A dry-run leaves the audit untouched via the existing `dry_run` guard. Targeted suites pass; ruff and ty clean.

## Notes

The investigation confirmed promote does write the audit, so this is a real mutation, not an invented one: the conditional refresh is correct rather than a no-op finding.
