---
tags:
  - '#exec'
  - '#vault-index-folder'
date: '2026-04-30'
modified: '2026-04-30'
related:
  - '[[2026-04-30-vault-index-folder-plan]]'
---

# `vault-index-folder` exec: phases 10-11 docs and live migration

Implements phases 10 and 11 of `[[2026-04-30-vault-index-folder-plan]]`.

## Summary

- Updated `README.md` so the document-types sentence mentions that
  generated feature indexes live in `.vault/index/` and are managed by
  `vault feature index`.
- Updated `.vaultspec/CLI.md` so the `vault feature index` section
  describes the canonical subfolder location and the `#index` directory
  tag.
- Updated `.vaultspec/rules/rules/vaultspec.builtin.md` (the source for
  the synced built-in rules) to add the index file to the documents list,
  add the feature-index entry to the documentation hierarchy, expand the
  allowed-tag set to seven directory tags, and add the `.vault/index/`
  row to the directory-tag table.
- Ran `vault check structure --fix` against this repo's own `.vault/`.
  The 55 legacy root-level `<feature>.index.md` files relocated into
  `.vault/index/` with the `#index` directory tag added to each one.
- Generated `.vault/index/vault-index-folder.index.md` so this PR's
  feature has its own index in the canonical location.

## Files touched

- `README.md`
- `.vaultspec/CLI.md`
- `.vaultspec/rules/rules/vaultspec.builtin.md`
- 55 vault index files renamed from `.vault/<feature>.index.md` to
  `.vault/index/<feature>.index.md`
- `.vault/index/vault-index-folder.index.md` (new)

## Tests

- `vaultspec-core vault check all` clean against the migrated repo.
- `pytest --deselect tests/test_mcp_config.py --deselect src/vaultspec_core/tests/cli/test_agents_render.py` clean.
- `ty check src/vaultspec_core` clean.
