---
tags:
  - '#research'
  - '#vault-index-folder'
date: '2026-04-30'
modified: '2026-04-30'
related: []
---

# `vault-index-folder` research: as-is index handling

Issue #91 proposes moving generated `<feature>.index.md` files out of the
`.vault/` root into a dedicated `.vault/index/` subfolder. This research
note inventories every code path, test, and document that currently hardcodes
the root-level location of feature index files, so the ADR and plan can
target a complete cutover.

## Findings

### inventory of index call sites

The vault-root location of `<feature>.index.md` is hardcoded in eight runtime
modules and two template/documentation surfaces.

`src/vaultspec_core/vaultcore/index.py`. `generate_feature_index` writes the
file to `docs_dir / f"{feature}.index.md"` and creates `docs_dir` if missing.
The single source of truth for index emission.

`src/vaultspec_core/vaultcore/checks/_base.py`. `is_generated_index` uses
filename suffix only (`path.name.endswith(".index.md")`) - location-agnostic.
Used by the structure, frontmatter, body-links, orphans, and features checkers
to skip index files (which have non-standard frontmatter: single feature tag,
no directory tag, `generated: true`).

`src/vaultspec_core/vaultcore/checks/features.py`. `_index_exists_for` matches
by exact filename `{feat_name}.index.md` across the entire snapshot - already
location-agnostic. `_count_index_related` filters by `is_generated_index` plus
stem parsing (`stem.removesuffix(".index")`). The stale-index warning and the
"no feature index" warning both work off these.

`src/vaultspec_core/vaultcore/scanner.py`. `get_doc_type` has explicit logic:
when a path has fewer than two parts relative to `docs_dir` (i.e. root-level),
it checks `.index.md` suffix and returns `DocType.INDEX`. This is the only
place that ties index classification to root-level location. `scan_vault`
walks `docs_dir.rglob("*.md")` so it already finds files in any subdirectory;
relocation does not require scanner rglob changes, only classification.

`src/vaultspec_core/vaultcore/models.py`.

- `DocType.INDEX = "index"` (string value, used by `get_doc_type` return).
- `VaultConstants.SUPPORTED_DIRECTORIES` excludes `INDEX` because it lives in
  the root - this is the line that needs to change.
- `VaultConstants.SUPPORTED_TAGS` similarly excludes `#index`.
- `validate_vault_structure` allows any `.index.md` file at root and rejects
  unknown subdirectories. Both clauses need updating.
- `validate_filename` regex pattern only accepts the six legacy doc-type
  suffixes; `.index.md` is exempted from filename validation by the
  `is_generated_index` check at the structure-checker level.

`src/vaultspec_core/vaultcore/hydration.py`. Template mapping
`DocType.INDEX: "index.md"` resolves the index template path under
`.vaultspec/rules/templates/index.md`. Location-agnostic; no change needed.

`src/vaultspec_core/vaultcore/checks/structure.py`. The structure checker
calls `is_generated_index` to skip index files from filename validation and
permits them under `validate_vault_structure`. Will need to learn about the
new subfolder so root-level legacy files are flagged as fixable.

`src/vaultspec_core/vaultcore/checks/body_links.py`. Skips index files via
`is_generated_index` - location-agnostic via filename. Test
`test_skips_index_files` constructs `root / ".vault" / "test-feature.index.md"`.

`src/vaultspec_core/vaultcore/checks/orphans.py`. Skips index files via
`is_generated_index` on `node.path`. Location-agnostic.

`src/vaultspec_core/vaultcore/checks/frontmatter.py`. Skips index files via
`is_generated_index`. Location-agnostic.

`src/vaultspec_core/cli/vault_cmd.py`. `cmd_feature_index` (lines 891-944)
calls `generate_feature_index` per feature; docstring claims the file lives
"in the vault root". Docstring needs updating; behaviour follows the
generator.

`src/vaultspec_core/vaultcore/resolve.py`. `_build_stem_index` walks
`scan_vault` which uses `rglob`; resolver is already flat-namespace-friendly.
No change needed for index relocation - wiki-link `[[<feature>.index]]`
resolution survives a directory move.

`src/vaultspec_core/testing/synthetic.py`. `_apply_stale_index` writes
`vault_dir / "plan" / f"{stem}.md"` where stem ends `.index`. The pathology
generator parks the stale index inside `plan/` (not the root) which is
already non-canonical. The `feature.index.md` references in docstrings
(line 380) describe it as a vault-root artifact. Migration needs to put
the stale-index pathology in the new index subfolder for fidelity.

### tests that touch index location

`src/vaultspec_core/vaultcore/tests/test_index.py`. Eight tests asserting
generation behaviour, including `test_creates_index_file` which checks
`path.name == "f.index.md"`. None bind to a specific subdirectory; they all
read the path returned by the generator.

`src/vaultspec_core/vaultcore/checks/tests/test_index_safety.py`. Six tests
constructing paths at `_ROOT / ".vault" / f"{feature}.index.md"`. Each will
need a parallel test variant or a parameterised path to validate
sub-folder-resolved index files.

`src/vaultspec_core/vaultcore/checks/tests/test_body_links.py`. Single test
constructing `root / ".vault" / "test-feature.index.md"`. Same migration.

`src/vaultspec_core/hooks/tests/test_hooks.py`. Contains the string `index`
only as part of an unrelated event name `vault.index.updated`. Out of scope.

### configuration surface

`src/vaultspec_core/config/config.py`. `VaultSpecConfig.docs_dir` is the
single configurable docs-root constant. The `framework_dir`, `claude_dir`,
`gemini_dir`, `antigravity_dir` knobs follow the same `DirName` enum pattern.
`ConfigVariable` in `CONFIG_REGISTRY` declares each settable attr with an
`env_name`, `attr_name`, `var_type`, `default`, `description`. Adding an
`index_dir` config knob fits this pattern naturally.

`src/vaultspec_core/core/enums.py`. `DirName` enum holds string constants for
`.vault`, `.vaultspec`, `.claude`, etc. The new index subfolder name belongs
here as a new `DirName.VAULT_INDEX = "index"` (relative to `docs_dir`) or as
a top-level config-only value, depending on the ADR decision.

### built-in rules and documentation surface

`.vaultspec/CLI.md`. Section `### vault feature index` (line 224) describes
indexes living "at the vault root". Needs rewording.

`.vaultspec/rules/templates/index.md`. The index template comment says
"index files live in .vault/ root". Needs rewording.

`.vaultspec/README.md`. Mentions `.vault/` subfolders but does not mention
indexes at the root. Will need a new bullet describing `.vault/index/`.

`README.md`. Lists six valid document types (`adr`, `audit`, `exec`, `plan`,
`reference`, `research`). If indexes get a new directory tag, the list needs
expanding; if they remain tagless-with-feature-only, a sentence is enough.

`.claude/rules/vaultspec.builtin.md` (parent-shared). The "Documentation
Hierarchy" lists six `.vault/` subdirectories. The "Tag Taxonomy" enumerates
six allowed tags plus `#{feature}`. The "Directory Tags" table maps six
directories to six tags. All three surfaces need updating.

`CLAUDE.md` (parent-shared). Includes the rules transitively via include
directives; no direct edits required.

### this repo's vault state

`.vault/` currently contains 55 root-level `<feature>.index.md` files
(verified via `ls .vault/*.index.md | wc -l`). Each will be relocated as the
final commit of this PR, exercising the migration on real data.

### tag taxonomy implications

The current taxonomy has six directory tags (`#adr`, `#audit`, `#exec`,
`#plan`, `#reference`, `#research`) plus the feature tag `#{feature}`.
Indexes today are special-cased: single feature tag, no directory tag,
`generated: true`. Two design paths emerge.

Option A: Add `#index` as a seventh directory tag. Indexes get the standard
"two-tags" shape (`#index` + `#feature`). Aligns with the "every document
in `.vault/` MUST include EXACTLY TWO tags" rule. Requires updating the
template, frontmatter checker exemption logic, `DocType.INDEX` in
`SUPPORTED_TAGS`, and every existing root index file.

Option B: Keep indexes tagless except for the feature tag. The new folder
becomes a special case in `VaultConstants` similar to `AUXILIARY_DIRECTORIES`
(`data/`, `logs/`). Less disruption to existing index files, more divergence
from the canonical "two-tags" rule.

Option A produces a more uniform taxonomy at the cost of mass-editing 55
existing index files (which the migration script can do automatically
alongside the move). The ADR will commit to Option A given the documentation
hierarchy already promises symmetry between subfolder and tag.

### migration semantics

The migration must:

- detect legacy root-level `.index.md` files in `.vault/`
- relocate to `.vault/index/<feature>.index.md`
- update frontmatter to add the `#index` directory tag (Option A)
- preserve `related:` fields and the body
- be exposed as a `vault check` finding with `--fix` support

Wiki-link resolution: `_build_stem_index` walks `scan_vault` which walks
`docs_dir.rglob`. A wiki-link `[[my-feature.index]]` resolves by stem
regardless of the file's parent directory. Existing `related:` references
to indexes survive the move with no rewrite needed.

The structure checker's `validate_vault_structure` rejects unknown
subdirectories, so `index/` must be added to `SUPPORTED_DIRECTORIES`. The
"file at root" branch must reject `.index.md` files going forward (currently
it accepts them); the auto-fix relocates them.

### summary of files to touch

Code: `vaultcore/index.py`, `vaultcore/scanner.py`, `vaultcore/models.py`,
`vaultcore/checks/_base.py` (add `is_generated_index_legacy` predicate),
`vaultcore/checks/structure.py` (add migration), `vaultcore/checks/features.py`
(point lookups at the new folder), `cli/vault_cmd.py` (docstring +
migration command surface), `core/enums.py` (`DirName`),
`config/config.py` (`index_dir`), `testing/synthetic.py` (stale-index pathology
location), `vaultcore/hydration.py` (no behaviour change; verify template
mapping still resolves).

Tests: `vaultcore/tests/test_index.py`, `vaultcore/checks/tests/test_index_safety.py`,
`vaultcore/checks/tests/test_body_links.py`, plus new tests for migration
auto-fix, scanner classification of subfolder index files, structure-checker
root-level legacy detection, and synthetic vault parity.

Docs and rules: `README.md`, `.vaultspec/CLI.md`, `.vaultspec/README.md`,
`.vaultspec/rules/templates/index.md`, `.claude/rules/vaultspec.builtin.md`
(parent-shared), and the live vault content (`.vault/*.index.md` -> `.vault/index/`).

### open questions for the ADR

- Is the index folder name configurable (like `docs_dir`) or hardcoded
  (like the `_archive`/`.obsidian` exemptions)?
- Does the new directory tag follow the `#index` form, or a different
  convention?
- Should the migration be silent (auto-fix without warning) or warn loudly
  on first encounter so users notice the layout change?
