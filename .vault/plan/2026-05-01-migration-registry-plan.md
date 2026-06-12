---
tags:
  - '#plan'
  - '#migration-registry'
date: '2026-05-01'
modified: '2026-05-01'
related:
  - '[[2026-05-01-migration-registry-adr]]'
  - '[[2026-05-01-migration-registry-research]]'
---

# `migration-registry` plan

Implement the registry per the ADR
`[[2026-05-01-migration-registry-adr]]`. The execution proceeds in one
phase because the registry is small enough to land coherently and
splitting it across phases would force partial-state code reviews.

## phase-1: implementation

### task-1: lift `parse_version_tuple` into `core/helpers.py`

Promote the private `_parse_version_tuple` from
`core/resolver.py` to the public `parse_version_tuple` in
`core/helpers.py`. Update `_resolve_version_warning` to use the new
location. The registry depends on this for version comparison without
importing from `core/resolver.py` (which would create a circular
import).

### task-2: registry skeleton

Create `src/vaultspec_core/migrations/__init__.py` with:

- `MigrationResult` dataclass (`name`, `target_version`, `summary`,
  `counts`)
- `Migration` dataclass (`target_version`, `name`, `migrate`)
- `MigrationStatus` enum (`UP_TO_DATE`, `PENDING`, `UNKNOWN`)
- `REGISTRY: list[Migration]` (initially empty; task-3 fills the
  first entry)
- `run_pending_migrations(workspace)` driver
- `pending_migrations(workspace)` read-only check used by doctor
- Per-process workspace cache so `scan_vault` does not re-trigger on
  every call

The driver bumps the manifest version on success only when at least
one migration ran.

### task-3: first migration entry

Create `migrations/m_0_1_17_index_subfolder.py`. Move the body of
`_migrate_legacy_root_indexes` over verbatim, reshaped to return a
`MigrationResult` instead of mutating a `CheckResult`. `_INDEX_TAG`,
`_TAG_ENTRY_RE`, and `_ensure_index_directory_tag` stay in
`structure.py` because the warning branch still uses them; the
migration imports them from there. Atomic-write semantics, CRLF
preservation, exact-match tag detection are preserved unchanged.

### task-4: `install_run` upgrade-branch trigger

Replace the `mdata.vaultspec_version = _get_package_version()` line in
`install_run` (upgrade branch only) with a `run_pending_migrations`
call. The driver writes the manifest after running entries; the
existing post-call `write_manifest_data(path, mdata)` still runs to
record the gitignore/precommit fields, but the migration driver may
have already bumped the version. Because the manifest is reread
between the two writes, the final `write_manifest_data` picks up the
post-migration version. We add an explicit reread to make this
visible.

### task-5: scanner lazy trigger

Insert `run_pending_migrations(root_dir)` near the top of `scan_vault`
in `vaultcore/scanner.py`. Guard with a per-process workspace cache so
multiple scans within the same invocation skip the manifest
read after the first call. Failure mode: if migration raises, the
exception propagates to the caller. We do not swallow.

### task-6: `migrations` CLI subcommand

Add a new `migrations` Typer sub-app at the root level with two
commands:

- `migrations status [--target T] [--json]`: prints current
  `vaultspec_version`, registered migrations, and pending migrations.
- `migrations run [--target T] [--json]`: invokes
  `run_pending_migrations` and prints per-entry summaries. Exit code
  1 if any migration raised.

Mounted in `cli/root.py` next to the `vault` and `spec` sub-apps.

### task-7: doctor integration

- Add `migration_status: MigrationStatus` and
  `pending_migrations: list[str]` to `WorkspaceDiagnosis`.
- Add `collect_migration_status(target)` to
  `core/diagnosis/collectors.py`.
- `diagnose()` runs the new collector when the framework is present.
- `cmd_doctor` adds a new table row "migration".
- `_doctor_exit_code` raises the warning-bit when status is
  `PENDING`.
- JSON output is additive: extra keys, no removed keys.

### task-8: drop mutation from `check_structure`

- Remove both `_migrate_legacy_root_indexes(... fix=True)` and
  `_migrate_legacy_root_indexes(... fix=False)` calls from
  `check_structure`.
- Replace with a non-mutating detection helper that emits one
  `WARN`-severity diagnostic per misplaced index pointing at
  `migrations run`. The detection logic is essentially the same
  `rglob` walk without the I/O. Place this helper in
  `vaultcore/checks/structure.py` next to the existing predicates.
- The aggregate `validate_vault_structure` "Legacy feature index"
  message stays but its language is updated to reference
  `migrations run`.
- Update `vaultcore/models.py:validate_vault_structure` accordingly.

### task-9: pre-commit hook docstring

Update `.pre-commit-hooks.yaml`. Drop the claim that `vault-fix`
performs migration ("schema") from the documentation block. The
recurring hook covers naming, frontmatter, links, dangling, and
references only.

### task-10: tests

#### Registry mechanics

`src/vaultspec_core/migrations/tests/test_registry.py`:

- empty registry: `run_pending_migrations` is a no-op, version
  unchanged
- single migration with `target_version > manifest.vaultspec_version`:
  runs once, version bumps, second run is a no-op
- two migrations with different target versions on a stale workspace:
  both run in version order
- manifest version equal to target version: no run
- migration that raises: version is not bumped, error propagates

#### First migration entry

`src/vaultspec_core/migrations/tests/test_index_subfolder.py`:

- legacy root index: relocated, `#index` tag inserted
- already-migrated workspace: no-op
- CRLF source: line endings preserved
- misplaced index in typed subdir: relocated

#### Trigger sites

`src/vaultspec_core/tests/cli/test_migration_triggers.py`:

- `install --upgrade` on legacy workspace: migration runs, version
  bumps
- `vault add adr foo` on legacy workspace: migration runs first, then
  the add succeeds
- `vault feature index -f foo` on legacy workspace: migration runs
  first, then writes new index. No split-brain (this is the headline
  bug)
- `vault check` (no `--fix`) on legacy workspace: warns, does not
  mutate
- `migrations status` lists pending migrations
- `migrations run` executes them and bumps the version
- after migration, `vault-fix`-equivalent (`vault check all --fix`)
  does not touch index files

### task-11: docs

- Update `README.md` to describe the migration model and the
  `migrations status` / `migrations run` commands.
- Update `.vaultspec/rules/builtin/vaultspec-cli.md` (if applicable).
- The new commands surface in the rendered Typer help output
  automatically.

## phase-2: verification

### task-12: code review

Run `vaultspec-core spec doctor`, `vault check all`, `pytest`,
`ty check src/vaultspec_core`, `ruff check`, `ruff format --check`.

### task-13: audit sweep

Per the issue:

1. grep for every `_migrate_legacy_root_indexes` reference; confirm
   each callsite is updated or removed
1. grep for every place that hardcodes the migration check; update
   to test via the registry
1. confirm `.pre-commit-hooks.yaml` no longer claims migration
1. confirm README and built-in rules describe the new model
1. confirm `spec doctor` JSON output includes `migration_status` and
   the schema change is backwards-compatible
1. confirm no migration-related code remains inside `vaultcore/checks/`

### task-14: PR finalisation

Push commits incrementally. Open at draft, request review from
gemini-code-assist, address findings, flip to ready when CI is green
and reviews are clean.
