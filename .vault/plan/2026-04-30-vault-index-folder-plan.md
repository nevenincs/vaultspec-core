---
tags:
  - '#plan'
  - '#vault-index-folder'
date: '2026-04-30'
related:
  - '[[2026-04-30-vault-index-folder-adr]]'
  - '[[2026-04-30-vault-index-folder-research]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

# `vault-index-folder` plan: dedicated index subfolder migration

Implementation plan for `[[2026-04-30-vault-index-folder-adr]]`. Each phase
ships as one commit on the feature branch with tests landing alongside the
code that calls them.

## Phase 1 - constants and config

Add `DirName.INDEX = "index"` to `core/enums.py`. Add `index_dir: str` to
`VaultSpecConfig` defaulting to `DirName.INDEX.value`. Register a
`ConfigVariable` entry in `CONFIG_REGISTRY` with env name
`VAULTSPEC_INDEX_DIR`. Add a config-test asserting the default value and the
override path. Code only - the new constant is unused at this point.

## Phase 2 - models, scanner, taxonomy

Update `vaultcore/models.py`:

- Extend `VaultConstants.SUPPORTED_DIRECTORIES` so `DocType.INDEX.value` is
  included.
- Extend `VaultConstants.SUPPORTED_TAGS` so `#index` is included.
- Update `validate_vault_structure` so files at the docs root with the
  `.index.md` suffix are reported as a violation (legacy location), and so
  the `index/` subdirectory is recognised.
- Update `validate_filename` so `.index.md` files are accepted in the
  `index/` subfolder. Filename pattern remains `<feature>.index.md` (no date
  prefix).

Update `vaultcore/scanner.py` `get_doc_type`:

- When the path's first part relative to `docs_dir` equals `index_dir`,
  return `DocType.INDEX`.
- Keep the existing root-level fallback for back-compat, but tighten it to
  log a debug message indicating "legacy root-level index" - this surfaces
  the migration need without breaking unmigrated vaults.

Update tests under `vaultcore/tests/test_scanner.py` and any model tests to
cover the new classification.

## Phase 3 - generator

Update `vaultcore/index.py`:

- Resolve the index target as `docs_dir / index_dir / f"{feature}.index.md"`.
- Ensure the index directory exists (`mkdir(parents=True, exist_ok=True)`).
- Add the `#index` directory tag to the rendered frontmatter alongside the
  feature tag.
- Drop the special case that skips the `generated: true` marker - the marker
  stays.

Update `vaultcore/tests/test_index.py`: every test that asserts
`path.name == "f.index.md"` keeps that assertion; add an assertion that
`path.parent.name == "index"`. Add a tag-shape assertion that the rendered
frontmatter contains both `#index` and `#<feature>`.

## Phase 4 - migration auto-fix in structure checker

Add a new helper in `vaultcore/checks/structure.py`:

- Walk `docs_dir` for `*.index.md` files whose parent equals `docs_dir`
  (root-level legacy indexes).
- For each one, emit a `CheckDiagnostic` with `severity=ERROR`,
  `fixable=True`, message describing the relocation, and
  `fix_description="Run with --fix to relocate to .vault/index/"`.
- When `fix=True`, perform the move:
  - Create `docs_dir / index_dir` if missing.
  - Atomic rename (`shutil.move` or filesystem-atomic write).
  - Rewrite frontmatter to insert `#index` directory tag if missing.
  - Bump `result.fixed_count` and append an INFO diagnostic.
  - On rename or rewrite failure, leave the file in place and emit an ERROR
    diagnostic.

Add tests under `vaultcore/checks/tests/test_structure.py` (or a new file
`test_index_migration.py`):

- Real filesystem fixture using `WorkspaceFactory`.
- Test: legacy root index detected as ERROR.
- Test: auto-fix relocates the file and adds `#index` tag.
- Test: idempotent - running `--fix` twice is a no-op.
- Test: collision with an existing `index/<feature>.index.md` reports an
  ERROR and does not overwrite.

## Phase 5 - features checker

Update `vaultcore/checks/features.py`:

- `_index_exists_for` already matches by filename; no functional change
  required, but the diagnostic message updates to mention the new path.
- The "no feature index" warning's `fix_description` becomes
  `"vault feature index -f {feat_name}"` (unchanged) since the generator now
  writes to the new location.

## Phase 6 - frontmatter / body-links / orphans

These three checkers all rely on `is_generated_index` (filename-based). No
behavioural change. Add a regression test in
`vaultcore/checks/tests/test_index_safety.py` that constructs index paths
both at root (legacy) and under `index/` (canonical) and asserts both are
skipped uniformly.

## Phase 7 - CLI

Update `cli/vault_cmd.py`:

- `cmd_feature_index` docstring: change "in the vault root" to "in
  `.vault/index/`".
- No behavioural change needed; the docstring is the only callsite that
  asserts the old location.

## Phase 8 - synthetic vault

Update `testing/synthetic.py`:

- `_apply_stale_index` writes the pathology under
  `vault_dir / "index" / f"{stem}.md"`.
- `pathology_details` keeps the same shape; the directory in the manifest
  changes from `plan` to `index`.
- Update the generator's docstring.

Add tests under `testing/tests/` if they exist, or extend the existing
synthetic-corpus assertions to verify the pathology lands in the expected
location.

## Phase 9 - template

Update `.vaultspec/rules/templates/index.md`:

- Add `#index` directory tag.
- Update the comment to say "index files live in `.vault/index/`".

## Phase 10 - documentation and built-in rules

`README.md`: update the document-types sentence to include `index` (or add
a sentence noting that indexes are auto-generated and live in
`.vault/index/`).

`.vaultspec/CLI.md`: section `### vault feature index` rewords "at the vault
root" to "in `.vault/index/`".

`.vaultspec/README.md`: add `index/` to the directory enumeration.

`.claude/rules/vaultspec.builtin.md` (parent-shared): add a row to the
"Directory Tags" table for `.vault/index/` -> `#index`. Update the "Tag
Taxonomy" allowed-tags list. Update the documentation hierarchy if it
enumerates folders.

## Phase 11 - migrate this repo's own vault

After phases 1-10 land and tests pass, run
`uv run --no-sync vaultspec-core vault check structure --fix` against the
worktree. The 55 root-level `*.index.md` files relocate to `.vault/index/`
with `#index` tags added. Commit the resulting tree as the final commit
("apply migration to this repo's vault").

## Phase 12 - quality gates

- `uv run --no-sync pytest` clean.
- `uv run --no-sync python -m ty check src/vaultspec_core` clean.
- `uv run --no-sync prek run --all-files` clean (modulo the pre-existing
  `spec-check` framework error which is out of scope).
- `uv run --no-sync vaultspec-core vault check all` clean against the
  migrated `.vault/`.
- PR body updated with vault artifact links and bot review status.

## Test policy reminders

- No mocks, patches, stubs, fakes, skips. Use `WorkspaceFactory` and the
  synthetic corpus.
- No tautological tests. Each test must fail against the wrong
  implementation.
- Real filesystem assertions only.
- Google-style docstrings with Sphinx cross-refs on all new public APIs.
- No em-dashes anywhere (use spaced hyphens).
