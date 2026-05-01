---
tags:
  - '#exec'
  - '#vault-index-folder'
date: '2026-04-30'
related:
  - '[[2026-04-30-vault-index-folder-plan]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

# `vault-index-folder` exec: phases 1-3 constants, scanner, generator

Implements phases 1-3 of `[[2026-04-30-vault-index-folder-plan]]`.

## Summary

- Added `DirName.INDEX` plus `VaultSpecConfig.index_dir` and registered the
  matching env var so the new index subfolder is the configurable single
  source of truth across the codebase.
- Updated the scanner so files inside `<docs_dir>/<index_dir>/` are
  classified as `DocType.INDEX`, while keeping the legacy root-level
  fallback so unmigrated vaults still classify their indexes.
- Updated the generator to write into the new subfolder and to render the
  standard two-tag shape (`#index` plus `#<feature>`).
- Extended `VaultConstants.SUPPORTED_DIRECTORIES` and
  `SUPPORTED_TAGS` to include the new directory and its tag, and
  reshaped `validate_vault_structure` to flag legacy root-level
  `*.index.md` files as violations.
- Updated `validate_filename` to recognise the
  `<feature>.index.md` shape inside the index subfolder.

## Files touched

- `src/vaultspec_core/core/enums.py`
- `src/vaultspec_core/config/config.py`
- `src/vaultspec_core/vaultcore/models.py`
- `src/vaultspec_core/vaultcore/scanner.py`
- `src/vaultspec_core/vaultcore/index.py`
- `src/vaultspec_core/config/tests/test_config.py`
- `src/vaultspec_core/vaultcore/tests/test_index.py`
- `src/vaultspec_core/vaultcore/tests/test_scanner.py`

## Tests

- `pytest src/vaultspec_core/config/tests/test_config.py` 13 passed.
- `pytest src/vaultspec_core/vaultcore/tests/test_index.py` 9 passed.
- `pytest src/vaultspec_core/vaultcore/tests/test_scanner.py` 12 passed.
- `pytest src/vaultspec_core/vaultcore` 121 passed.
- `ty check src/vaultspec_core` clean.
- `ruff check / format` clean.
