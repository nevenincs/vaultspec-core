---
tags:
  - '#reference'
  - '#uniform-rename'
date: '2026-06-26'
modified: '2026-06-27'
related:
  - "[[2026-06-26-uniform-rename-research]]"
---

# `uniform-rename` reference: `existing rename machinery and feature binding surfaces`

This reference maps the existing rename, move, and feature-tag machinery in
vaultspec-core so the new uniform feature-rename backend can reuse hardened code
rather than reinvent it. Sources are cited as `path:line`. The deliverable is
the binding-surfaces inventory at the end: every physical location a feature
name appears and the mechanism that can rewrite it.

## Summary

### Feature enumeration and extraction

A document belongs to feature X through exactly one non-directory tag in its
`tags:` list. Two independent code paths read this:

- `_parse_feature_from_tags` in `src/vaultspec_core/vaultcore/query.py:61` returns
  the first non-`DocType` tag with its leading `#` stripped, with a fallback to a
  bare `feature:` field at `query.py:107`. `list_documents`, `get_stats`, and
  `unarchive_feature` all rely on it; the `list_documents` filter normalises by
  stripping a leading `#` before comparing (`query.py:163`).
- `_extract_feature` in `src/vaultspec_core/graph/api.py:238` is the graph-side
  equivalent but sorts the tag set for determinism, so a (non-conformant) doc
  with two non-directory tags would resolve its feature differently than the
  query path. The frontmatter validator enforces exactly one feature tag
  (`src/vaultspec_core/vaultcore/models.py:338`), so conformant vaults are safe.

### archive_feature / unarchive_feature (closest sibling)

`archive_feature` (`query.py:298`) enumerates a feature's docs via
`list_documents(root, feature=...)`, queries `VaultGraph` for cross-feature
incoming links (`query.py:338`, the same analysis a rename needs), then
`shutil.move`s each doc under `.vault/_archive/` preserving its subdirectory.
`unarchive_feature` (`query.py:379`) walks the archive, re-parses each file's
feature tag, and moves matching files back, then prunes empty dirs.

Key gap: archive is a pure move. It does not rewrite filenames, frontmatter
tags, `related:` links, or the index. A rename must do all of that in addition
to the move. Note also that `.vault/_archive/` is excluded from scans
(`src/vaultspec_core/vaultcore/scanner.py`), so archived docs of the same
feature are invisible to a rename.

### Structure-rename cascade (reusable engine)

`src/vaultspec_core/vaultcore/checks/structure.py` already contains the two
primitives a feature rename needs:

- `_rename_document_path` (`structure.py:57`) renames a file and handles
  case-only renames on case-insensitive filesystems via a UUID temp-file two-hop;
  returns `False` when the destination is a different existing file.
- `_rewrite_incoming_refs` (`structure.py:256`) rewrites old-stem wiki-links to
  new-stem wiki-links across the whole docs tree, scoped strictly to the
  `related:` frontmatter block. It collapses rename chains and drops cycles
  (`structure.py:296`), dedups colliding targets, preserves CRLF and UTF-8 BOM
  byte-for-byte (`structure.py:356`), preserves anchors/aliases, and re-reads
  from disk after the renames land. Body prose is never touched.

Hard limits to carry into the design: it does not rewrite YAML flow-style
`related:` lists (the inline bracketed form, see `structure.py:271`), and it has
a 200-line frontmatter budget. `check frontmatter` enforces block style, so conformant
vaults are unaffected.

### Per-field related: surgery with rollback

`src/vaultspec_core/vaultcore/related_surgery.py` provides
`remove_related_entries` / `append_related_entry` with a `.bak`-based
`_atomic_write_restore` rollback (`related_surgery.py:75`) and a flow-to-block
`related:` normaliser (`related_surgery.py:251`) - a reusable pattern for the
tag-block rewriter and a model for journalled rollback.

### Single-document rename precedent

`_execute_rename` in `src/vaultspec_core/cli/edit_cmd.py` (around `edit_cmd.py:818`)
already sequences "rewrite incoming links -> filesystem rename -> refresh
modified stamp" for one document. It is the precedent for "rename plus re-point
links as one verb", but it sets an arbitrary stem and does not understand the
feature segment, the exec folder, or the index.

### rename_integrity check (spec-resource scope only)

`check_rename_integrity` (`src/vaultspec_core/vaultcore/checks/rename_integrity.py:35`)
enforces filename \<-> frontmatter `name:` agreement for
`.vaultspec/rules/{rules,skills,agents}/` resources. `--fix` rewrites the
frontmatter (filename wins); `--fix-frontmatter-wins` calls `resource_rename`
to move the file. It does not look at `.vault/` feature tags at all, so feature
drift is currently unchecked.

### Spec resource rename primitive

`resource_rename` (`src/vaultspec_core/core/resources.py:186`) is the atomic
rename for spec resources: flat files write-new-then-unlink-old with rollback;
directory resources `shutil.move` then rewrite `SKILL.md`, moving back on
failure. It is the clean source-of-truth pattern the cli-rename-integrity ADR
established, at single-resource scope.

### Feature index generation

`generate_feature_index` (`src/vaultspec_core/vaultcore/index.py:25`), invoked by
`cmd_feature_index` (`vault_cmd.py:1931`), writes
`<docs_dir>/<index_dir>/<feature>.index.md` (no date prefix), with
`tags: ['#index', '#{feature}']`, a `related:` block of every feature node, and
a body heading `` # `{feature}` feature index ``. It is idempotent (byte-compare
before write). The feature name appears three times inside the file plus in the
filename, so a rename must delete the old index and regenerate the new one.

### CLI feature group

`feature_app` is registered at `src/vaultspec_core/cli/vault_cmd.py:37` with
`list`, `index`, `archive`, `unarchive`. `archive`/`unarchive` take a positional
`feature_tag` plus `--dry-run` / `--json` / `--no-hints` (no `--force`). A new
`rename` command slots in after `unarchive` (around `vault_cmd.py:2112`) with two
positionals plus `--dry-run` / `--json` / `--force` / `--no-hints`; the backend
belongs in `query.py` beside `archive_feature`.

### Validation and naming

- Filename grammar: `VaultConstants.validate_filename` (`models.py:514`) matches
  `YYYY-MM-DD-<feature>-<type>.md`; the feature is the segment between the date
  prefix and the type suffix. Index files use a separate
  `^[a-z0-9-]+\.index\.md$` pattern.
- Feature-tag kebab-case gate at `vault add` time: `^[a-z0-9][a-z0-9-]*$`
  (`vault_cmd.py:243`); the schema tag form is `^#[a-z0-9-]+$` (`models.py:345`).
- Exec folder is `{plan_date}-{feature}` and exec records are
  `{plan_date}-{feature}-{suffix}.md` / `...-summary.md`
  (`src/vaultspec_core/vaultcore/hydration.py:417`). The date is the parent
  plan's date and must be preserved verbatim; only the feature segment changes.

### Binding surfaces inventory

Every place a feature name is physically present and must change on rename:

| Surface                                                    | Carries feature                                        | Rewrite mechanism                   |
| :--------------------------------------------------------- | :----------------------------------------------------- | :---------------------------------- |
| Authored doc filenames (adr/audit/plan/reference/research) | segment between date and type suffix (`models.py:571`) | `_rename_document_path`             |
| Exec folder `.vault/exec/{date}-{feature}/`                | date-feature suffix (`hydration.py:422`)               | `shutil.move`                       |
| Exec record filenames                                      | between date and step/phase id (`hydration.py:417`)    | `_rename_document_path` per file    |
| Frontmatter `tags: ['#feature']`                           | the tag value (`query.py:61`)                          | new tag-block rewrite pass          |
| `related:` wiki-link stems                                 | embedded in stem                                       | `_rewrite_incoming_refs` (reusable) |
| Body wiki-links                                            | forbidden by schema (`checks/body_links.py`)           | none (pre-check guards)             |
| Index filename `{feature}.index.md`                        | file stem prefix (`index.py:58`)                       | delete + regenerate                 |
| Index tags + heading + related                             | three occurrences (`index.py:58,96,103`)               | `generate_feature_index`            |
| Exec `related:` plan-stem entry                            | plan stem contains feature (`exec-step.md:9`)          | `_rewrite_incoming_refs` (reusable) |
| Exec `step_id:`                                            | canonical id only, no feature                          | none                                |
| Exec `## Scope` block                                      | source-code paths only, no feature                     | none                                |

### Testing conventions

The CI gate is `pytest src/vaultspec_core -m unit`. Query tests live in
`src/vaultspec_core/vaultcore/tests/test_query.py`; structure-rename tests in
`.../checks/tests/test_structure_case_rename.py`. CLI-level tests use the
`WorkspaceFactory` fluent builder at
`src/vaultspec_core/tests/cli/workspace_factory.py`; the
`vaultspec_core.testing.synthetic` generator supplies corpora (never commit
fixtures).
