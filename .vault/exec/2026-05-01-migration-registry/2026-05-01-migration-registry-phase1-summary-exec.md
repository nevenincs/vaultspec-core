---
tags:
  - '#exec'
  - '#migration-registry'
date: '2026-05-01'
related:
  - '[[2026-05-01-migration-registry-plan]]'
  - '[[2026-05-01-migration-registry-adr]]'
  - '[[2026-05-01-migration-registry-research]]'
---

# `migration-registry` phase-1 summary

Phase 1 implementation landed in commit `fdc0609` on
`feature/95-migration-registry` (rebased onto current `main` after
PR #92 squash-merged). All plan tasks are complete; the
verification-phase audit sweep follows.

## tasks shipped

- task-1: lifted `parse_version_tuple` from `core/resolver.py` to
  `core/helpers.py`. The empty-string case parses to `()` so the
  empty-manifest case sorts strictly below any real version.
- task-2: registry skeleton in
  `src/vaultspec_core/migrations/__init__.py` with
  `MigrationResult`, `Migration`, `MigrationStatus`,
  `run_pending_migrations`, `list_pending`, `migration_status`, and
  `reset_workspace_cache`. The driver bumps the manifest to
  `max(running_version, highest_pending_target)` so the version
  cannot regress below an applied migration.
- task-3: first migration entry in
  `src/vaultspec_core/migrations/m_0_1_17_index_subfolder.py`,
  porting the structure-checker helper byte-for-byte. CRLF
  preservation, exact-match `#index` tag detection, and atomic
  relocate semantics are unchanged.
- task-4: `install_run` upgrade-branch trigger added before the
  manifest-rewrite block. The install path now reads the migrated
  manifest and refuses to downgrade `vaultspec_version`.
- task-5: lazy trigger inside `scan_vault` with a per-process
  workspace cache so the manifest read happens once per CLI
  invocation. Failures propagate.
- task-6: `vaultspec-core migrations status` and
  `vaultspec-core migrations run` CLI commands in
  `src/vaultspec_core/cli/migrations_cmd.py`, mounted in
  `cli/root.py`.
- task-7: `WorkspaceDiagnosis` carries `migration_status` and
  `pending_migrations`; `diagnose()` populates them via the registry
  helper; `cmd_doctor` adds a "migration" row; `_doctor_exit_code`
  flips the warning bit when status is pending.
- task-8: dropped both `_migrate_legacy_root_indexes` callsites from
  `check_structure`. The new `_detect_legacy_root_indexes` helper
  emits one WARNING per misplaced file pointing at
  `vaultspec-core migrations run`. The aggregate
  `validate_vault_structure` legacy message also points at
  `migrations run`.
- task-9: `.pre-commit-hooks.yaml` docstring updated to drop the
  schema-migration claim. The recurring `vault-fix` hook covers
  ongoing hygiene only.
- task-10: 44 new tests covering registry mechanics, the
  index_subfolder entry, and the three trigger sites including the
  headline split-brain bug fix.
- task-11: README gains a `Schema migrations` section;
  `.vaultspec/CLI.md` gains a `Migration Commands` group;
  `.vaultspec/rules/rules/vaultspec-cli.builtin.md` mentions the
  new commands.

## post-rebase notes

PR #92 squash-merged into `main` while phase 1 was in progress. The
branch was reset to `origin/main` and the registry work re-applied
on top. PR #94 (the spec-check false-positive fix for #93) had also
merged, so the implementation commit passes every pre-commit hook
without `--no-verify`. Only the two earlier docs commits used
`--no-verify`, both as documented on those commit messages.

## quality gates

- `ruff check .`: passes
- `ruff format --check .`: passes (180 files)
- `ty check src/vaultspec_core`: passes
- `pytest --ignore tests/test_mcp_config.py --ignore src/vaultspec_core/tests/cli/test_agents_render.py`:
  1383 passed (the two ignored tests are pre-existing
  environmental failures unrelated to this work)
- `vaultspec-core vault check all`: clean
- `vaultspec-core spec doctor`: framework ok, migration row ok

## next: phase-2 verification

Phase-2 tasks remaining: gemini review loop, audit sweep
confirmation, and merge.
