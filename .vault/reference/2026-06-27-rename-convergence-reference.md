---
tags:
  - '#reference'
  - '#rename-convergence'
date: '2026-06-27'
modified: '2026-06-27'
related:
  - "[[2026-06-26-uniform-rename-adr]]"
---

# `rename-convergence` reference: `rename surfaces, shared primitives, lock, and integrity-check landscape`

This reference maps every rename/move CRUD in the CLI and the safety properties each
currently has, so the work of converging them onto the hardened engine that
`vault feature rename` already uses can be grounded in exact locators. Sources are cited
as `path:line`.

## Summary

### The four rename surfaces

There is not one rename pattern but four, and only `rename_feature` is hardened.

- `resource_rename` (`src/vaultspec_core/core/resources.py:186`) - the spec
  rules/skills/agents rename. Flat resources: `atomic_write` new then `unlink` old
  (`resources.py:284`); skills: `shutil.move` the dir then rewrite `SKILL.md`
  (`resources.py:242`). Rewrites the frontmatter `name:` only; ad-hoc move-back/unlink on
  failure (logged, not guaranteed). Callers: `spec rules/skills/agents rename`
  (`cli/spec_cmd.py:473,774,1071`) and `check_rename_integrity --fix-frontmatter-wins`
  (`checks/rename_integrity.py:277`).
- `_execute_rename` (`src/vaultspec_core/cli/edit_cmd.py:818`) - the document `vault rename` verb. Computes `new_path = old.parent / f"{new_stem}.md"` (`edit_cmd.py:876`),
  rewrites incoming links via a SECOND implementation (`remove_related_entries` +
  `_add_related_link`, `edit_cmd.py:806`) found through graph `out_links`, then
  `old_path.replace(new_path)` (`edit_cmd.py:908`). Refreshes the renamed doc's stamp
  with newline preservation (`edit_cmd.py:909`). Per-doc blob-hash OCC, no lock, no
  rollback. CLI: `register_rename_command` (`edit_cmd.py:948`).
- `rename_feature` (`src/vaultspec_core/vaultcore/query.py:1467`) - the hardened
  reference: containment guard `_assert_within_docs` (`query.py:517`), reverse-journal
  (`_RenameJournal` `query.py:587`, `_snapshot_docs` `:1208`, `_apply_rename_plan`
  `:1362`, `_rollback_rename` `:1312`, `_safe_restore_bytes` `:550`), symlink-skips,
  shared primitives, modified-stamp refresh. No advisory lock.
- `hooks_rename` (`src/vaultspec_core/core/hooks.py:239`) - a fourth, unhardened path:
  `shutil.move` a hooks YAML, no rollback, no lock, no containment.

### Shared primitives (the engine substrate already extracted)

`src/vaultspec_core/vaultcore/rename_ops.py`: `rename_document_path` (`:111`, case-safe
two-hop), `rewrite_incoming_refs` (`:166`, `related:` cascade, symlink-skip, CRLF/BOM
fidelity), `split_keepends` (`:51`, line-ending-preserving splitter). The structure
check shares `rename_document_path`/`rewrite_incoming_refs`
(`checks/structure.py:19-20,430`); `test_structure_case_rename.py` is the standing
regression gate for them.

### Advisory lock

`advisory_lock(path)` (`src/vaultspec_core/core/helpers.py:40`) locks a sibling
`<path>.lock` via a per-path `threading.Lock` plus an OS lock (`fcntl.flock` /
`msvcrt.locking`), and SKIPS locking when the lock file's parent dir is absent
(`helpers.py:59`). Every current caller locks the single config file it mutates -
`.gitignore` (`core/gitignore.py:210`), `.mcp.json` (`core/mcps.py:520,663`),
`.pre-commit-config.yaml` (`core/commands.py:539`), the manifest
(`migrations/__init__.py:334`, `core/manifest.py:66`). No rename path takes any lock. It
only serializes callers that share the SAME target. `.vault/data/` and `.vault/logs/`
and `.vaultspec/*.lock` are already gitignored (`core/gitignore.py:50,55-56`).

### rename-integrity check (model for the feature-scoped one)

`check_rename_integrity` (`src/vaultspec_core/vaultcore/checks/rename_integrity.py:35`)
enforces filename-stem vs frontmatter `name:` agreement for rules/skills/agents under
`.vaultspec/` and active provider mirrors; ERROR on mismatch; `--fix` (filename-wins,
rewrites `name:`) and `--fix-frontmatter-wins` (calls `resource_rename`). Scoped to
`.vaultspec/`, not `.vault/`. Has no dedicated unit tests. A feature-scoped analogue must
detect drift `check_features`/`check_structure` do not already own (see the research).

### Divergence map (the convergence gap)

| Property                 | resource_rename  | \_execute_rename    | rename_feature    | hooks_rename |
| :----------------------- | :--------------- | :------------------ | :---------------- | :----------- |
| Containment guard        | no               | no                  | yes (docs-dir)    | no           |
| Reverse-journal rollback | partial (logged) | none                | yes (byte-exact)  | none         |
| Advisory lock            | no               | no                  | no                | no           |
| Symlink-skip             | no               | no                  | yes               | no           |
| Line-ending fidelity     | no               | partial             | yes               | no           |
| Case-only rename safe    | no               | no                  | yes               | no           |
| Shared link cascade      | n/a              | no (duplicate impl) | yes               | n/a          |
| Modified-stamp refresh   | no               | yes (renamed doc)   | yes (all touched) | no           |

### Two concrete defects in `vault rename`

1. It rewrites incoming `related:` links FIRST (`edit_cmd.py:907`) then renames the file
   SECOND (`:908`) with no rollback - a failure between leaves dangling links into a
   stem that no longer exists, the exact drift the pipeline forbids.
1. It is a parallel link-rewrite implementation, reintroducing the duplication the
   uniform-rename ADR's shared-module extraction removed; the CRLF/BOM/chain/cycle/dedup
   hardening in `rename_ops.py` does not protect this path.

### Test gate

CI gate `pytest src/vaultspec_core -m unit`. Existing rename tests: `rename_feature`
(`vaultcore/tests/test_rename_feature{,_security,_encoding}.py`,
`tests/cli/test_feature_rename_cli.py`), `vault rename`
(`tests/cli/test_vault_rename.py`), structure cascade
(`checks/tests/test_structure_case_rename.py`). `resource_rename`, `hooks_rename`, and
`check_rename_integrity` have NO dedicated rename-logic unit tests - a coverage gap this
work should close.
