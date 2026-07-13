---
tags:
  - '#exec'
  - '#vault-orientation'
date: '2026-06-12'
modified: '2026-06-13'
step_id: S30
related:
  - '[[2026-06-12-vault-orientation-plan]]'
---

# document the modified field in the frontmatter schema and tag sections

## Scope

- `src/vaultspec_core/builtins/rules/vaultspec.builtin.md`

## Description

- Add `modified:` to the Tag Format example frontmatter block, set equal to `date:`.
- Add a two-sentence note describing `modified:` as a CLI-maintained last-modified
  stamp: set at scaffold, refreshed by mutating verbs and by check-fix, lenient-parsed
  but canonically `yyyy-mm-dd` quoted, never hand-edited.
- Add a `modified` row to the Frontmatter Placeholders table.
- Reflow the file with mdformat at wrap 88.

## Outcome

The frontmatter schema surface in
`src/vaultspec_core/builtins/rules/vaultspec.builtin.md` now documents the `modified:`
field everywhere frontmatter is described, per ADR decisions D3a and D3. The note stays
descriptive and does not restate the CLI-enforced discipline beyond identifying the
field's ownership.

## Notes

None.
