---
tags:
  - '#exec'
  - '#vault-orientation'
date: '2026-06-12'
modified: '2026-06-12'
step_id: S03
related:
  - '[[2026-06-12-vault-orientation-plan]]'
---

# stamp modified equal to date at scaffold time in document hydration

## Scope

- `src/vaultspec_core/vaultcore/hydration.py`

## Description

- Add `_inject_modified` to `src/vaultspec_core/vaultcore/hydration.py`: insert `modified: '<date>'` (canonical quoted form, equal to the creation date) directly after the `date:` line in the frontmatter block
- Call the injector from `hydrate_template` after placeholder substitution so every scaffolded document is stamped regardless of whether the deployed template carries the schema row yet
- Skip injection when the template already renders a `modified:` field, keeping the change forward-compatible with the template rows landing in the next phase

## Outcome

Every document scaffolded through `create_vault_doc` carries `modified:` equal to `date:`; verified live by scaffolding this step record, whose frontmatter shows the stamp, and by `vaultspec-core vault check all` reporting frontmatter clean. All 208 vaultcore tests pass; ruff format, ruff check, and ty check are clean.

## Notes

Step records scaffolded before this change (S01, S02 of this phase) predate the stamp; the W01.P04 backfill migration covers them.
