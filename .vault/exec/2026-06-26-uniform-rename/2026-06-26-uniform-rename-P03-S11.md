---
tags:
  - '#exec'
  - '#uniform-rename'
date: '2026-06-26'
modified: '2026-06-27'
step_id: 'S11'
related:
  - "[[2026-06-26-uniform-rename-plan]]"
---

# Render human output with renamed count, old-to-new paths, cross-link rewrite count, collision warnings, and a next-step hint

## Scope

- `src/vaultspec_core/cli/vault_cmd.py`

## Description

- Rendered dry-run output: header line naming old and new feature, planned-rename count, old-to-new path list, exec-folder rename list, predicted tag and related-link rewrite counts, and cross-feature incoming-link list (or "none found" confirmation).
- Rendered real-rename output: success line with count, path list, exec-folder renames, and a summary of tag and cross-feature related-link rewrites.
- Emitted the next-step hint via `emit_next_step_hint("vault.feature.rename", ...)` - hint text suggests running `vault check all`; respects `--no-hints` and `VAULTSPEC_NO_HINTS`.

## Outcome

Smoke test confirmed: human dry-run output is readable; real rename output prints the path list and counts; the next-step hint fires on success and is suppressed by `--no-hints`.

## Notes

No `render_listing` table is used for the path list - the sibling `archive`/`unarchive` commands print paths as plain lines, and this command mirrors that pattern rather than introducing a table.
