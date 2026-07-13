---
tags:
  - '#exec'
  - '#vault-orientation'
date: '2026-06-12'
modified: '2026-06-13'
step_id: S33
related:
  - '[[2026-06-12-vault-orientation-plan]]'
---

# add modified to the curator's allowed frontmatter keys with the lenient-parse repair note

## Scope

- `src/vaultspec_core/builtins/agents/vaultspec-docs-curator.md`

## Description

- Add `modified` to the Class A Unsupported Properties allowed-keys list so the curator
  recognizes the stamp as a supported frontmatter key.
- Add a stamp-repair sentence directing noncanonical or stale `modified:` values to
  `vaultspec-core vault check all --fix` rather than hand edits.
- Reflow the file with mdformat at wrap 88.

## Outcome

The curator persona in `src/vaultspec_core/builtins/agents/vaultspec-docs-curator.md`
now lists `modified` among its allowed frontmatter keys and routes stamp drift through
the lenient-parse check-fix path, satisfying ADR decision D3a. This keeps the curator
from flagging the CLI-maintained stamp as an unsupported property and points repair at
the CLI rather than manual editing.

## Notes

None.
