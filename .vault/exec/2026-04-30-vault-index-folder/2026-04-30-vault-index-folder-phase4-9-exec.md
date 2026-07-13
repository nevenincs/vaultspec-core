---
tags:
  - '#exec'
  - '#vault-index-folder'
date: '2026-04-30'
modified: '2026-06-13'
related:
  - '[[2026-04-30-vault-index-folder-plan]]'
---

# `vault-index-folder` exec: phases 4-9 migration, checkers, template

Implements phases 4 through 9 of `[[2026-04-30-vault-index-folder-plan]]`.

## Summary

- Added the legacy-index migration helper in the structure checker.
  Without `--fix`, every root-level `*.index.md` file is reported as a
  fixable ERROR. With `--fix`, files relocate into
  `<docs_dir>/<index_dir>/`, the YAML `tags:` block gains the `#index`
  directory tag if missing, and the move is atomic. Collisions surface
  as ERROR with the canonical file left untouched.
- Verified `is_generated_index` remains filename-based; the body-links,
  frontmatter, and orphans checkers continue to skip indexes
  uniformly. Extended `test_index_safety.py` to assert both legacy and
  canonical layouts are skipped.
- Updated the features check diagnostic message to reference
  `index/<feature>.index.md` while keeping the filename-based
  `_index_exists_for` predicate so the staleness logic is unaffected.
- Reworded the `vault feature index` CLI docstring.
- Relocated the `_apply_stale_index` synthetic pathology into the new
  `index/` subfolder and gave it the `#index` tag.
- Updated `.vaultspec/rules/templates/index.md` to render the
  `#index` directory tag and reflect the new home.

## Files touched

- `src/vaultspec_core/vaultcore/checks/structure.py`
- `src/vaultspec_core/vaultcore/checks/features.py`
- `src/vaultspec_core/vaultcore/checks/tests/test_index_safety.py`
- `src/vaultspec_core/vaultcore/checks/tests/test_index_migration.py` (new)
- `src/vaultspec_core/cli/vault_cmd.py`
- `src/vaultspec_core/testing/synthetic.py`
- `.vaultspec/rules/templates/index.md`

## Tests

- `pytest src/vaultspec_core/vaultcore/checks/tests/test_index_migration.py`
  8 passed.
- `pytest src/vaultspec_core/vaultcore/checks` 40 passed.
- `pytest src/vaultspec_core` 1180 passed (1 pre-existing failure in
  `test_agents_render` unrelated to this PR; 1 pre-existing failure in
  `test_mcp_config` because the source repo legitimately has no
  `.mcp.json`).
- `ty check src/vaultspec_core` clean.
- `ruff check / format` clean.
