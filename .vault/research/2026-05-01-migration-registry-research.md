---
tags:
  - '#research'
  - '#migration-registry'
date: '2026-05-01'
related:
  - '[[2026-04-30-vault-index-folder-research]]'
  - '[[2026-04-30-vault-index-folder-adr]]'
---

# migration-registry research

## context

PR #92 (issue #91) introduces the `.vault/index/` subfolder and ships a
migration helper `_migrate_legacy_root_indexes` inside the structure
checker. Because the `vault-fix` pre-commit hook calls
`vault check all --fix`, the migration helper re-runs on every commit,
forever. The user has stated explicitly that adding "one hook per dev
iteration" is unacceptable. We need a versioned migration registry that
runs once per upgrade (or lazily on first use of a vault command) and
then never re-runs.

A second motivator: even with PR #92 in place, the unmigrated state
leaves an active split-brain bug. `vault feature index -f foo` writes
the new index to `.vault/index/foo.index.md` while the legacy
`foo.index.md` at the docs root remains orphaned. Users then have two
files with the same logical identity and no migration path that the
generator itself knows about. The registry must run before any vault
command that mutates the index layout.

## current-state survey

### `_migrate_legacy_root_indexes` callsites

Located in `src/vaultspec_core/vaultcore/checks/structure.py` at line
531\. Two callsites in the same module:

- Line 719 inside `check_structure(... fix=True)`: performs the
  relocation before `validate_vault_structure` runs, so the post-fix
  pass observes the new tree.
- Line 741 inside `check_structure(... fix=False)`: detection-only,
  emits a per-file `ERROR` diagnostic with `fixable=True`.

The helper itself is pure with respect to filesystem boundaries: reads
bytes, decodes, calls `_ensure_index_directory_tag`, writes via
`atomic_write`, and unlinks the legacy file. The surrounding
`check_structure` callsite is the only thing that mutates `CheckResult`.
The mutation logic is naturally portable; the diagnostic emission stays
in `check_structure` as a warning when migration is pending.

### version handling

`core/resolver.py:876` defines `_parse_version_tuple(version_str)`
which strips PEP 440 suffixes and produces `tuple[int, ...]`. The
function is private; the registry needs the same logic. Since the
registry lives in a separate package, the cleanest answer is to
re-export `_parse_version_tuple` as `parse_version_tuple` (public name)
or move it to `core/helpers.py`. The existing `_resolve_version_warning`
already compares manifest version against running version using this
helper, which is exactly the comparison the registry needs.

`_get_package_version` is defined in `core/commands.py:53`. Reads
`importlib.metadata.version("vaultspec-core")` and returns
`"unknown"` on failure. The registry will use the same helper to set
the post-migration manifest version.

### manifest fields

`src/vaultspec_core/core/manifest.py` models `ManifestData`
with `vaultspec_version: str = ""`. The field is read by
`read_manifest_data` and written by `write_manifest_data` (which
auto-bumps `serial`). All four `install_run` paths bump the version
already (lines 946, 1066, 1698, 1750).

The empty default is significant: a fresh workspace has
`vaultspec_version=""`. The registry must treat empty as "lower than
any real version" so the first install on a brand-new workspace also
runs all entries, but only as a side effect of `_get_package_version`
already being written by `install_run`. We will keep the existing
contract: an installed workspace always has a non-empty version after
install. The registry is invoked after install seeds the version, so
it is a no-op for fresh installs.

### trigger sites

Three viable insertion points were considered.

**`install_run` upgrade branch**
(`src/vaultspec_core/core/commands.py` line 911-974). After
re-seeding builtins, before `write_manifest_data`. Already mutates the
manifest, already bumps `vaultspec_version`. Ideal place to run the
registry: when the user explicitly asks for an upgrade, we honour the
schema bump.

**`install_run` first-install branch** (line 1066). Less interesting:
a brand-new install has no legacy state to migrate. The registry will
no-op because the version is bumped to the running version before we
ever look. Still cheap, so we leave the call site for symmetry.

**Scanner / graph load**
(`src/vaultspec_core/vaultcore/scanner.py` `scan_vault` and
`src/vaultspec_core/vaultcore/query.py` `_scan_all`). Every
`vault` command opens the graph, which calls `scan_vault`. Inserting
the registry inside `scan_vault` covers `vault add`, `vault list`,
`vault check`, `vault feature index`, `vault stats`, and any future
command. The cost when up-to-date is one version-tuple compare. The
correctness when behind is automatic.

The chosen insertion point is `scan_vault`. `query._scan_all` and
`graph.api.VaultGraph._build_graph` both call `scan_vault`, so a single
hook covers both layers.

**CLI escape hatch**: `vaultspec-core migrations status` (read-only)
and `vaultspec-core migrations run` (explicit trigger). Lives at the
root command level for discoverability. Useful for users who do not
trust auto-migration and want to see what would change.

### the `vault-fix` recurring-hook problem

`.pre-commit-hooks.yaml` defines `vault-fix` as
`vaultspec-core vault check all --fix` on `types: [markdown]`. Every
markdown commit runs all checkers including structure, which today
triggers `_migrate_legacy_root_indexes`. After the registry takes over,
the structure checker keeps detection (warns) but never mutates. The
`vault-fix` hook stays as ongoing-hygiene (naming, frontmatter,
links). Migration leaves it.

## prior art

### Alembic

SQLAlchemy's Alembic uses an ordered chain of revision files keyed by
opaque hash IDs. Each revision has `down_revision` pointing to its
predecessor. The runtime stores the current revision in a database
table. On startup, Alembic walks from current to head applying every
intermediate revision.

Lessons applicable here:

- Each migration is its own module file. Reviewable in isolation.
- Migrations are append-only: a released migration is never edited.
- Idempotence is a property of the migration body, not the runtime.
- Linear order matters; concurrent merges with branched chains require
  manual resolution.

We do not need the full DAG: a single linear chain keyed by target
release version is enough for our scale. PEP 440 version strings give
us natural ordering without inventing hash IDs.

### Django migrations

Django's `django.db.migrations` uses an explicit dependency graph and
a `django_migrations` table. Auto-generated migration filenames
combine an integer prefix and a slug
(`0001_initial.py`, `0002_add_user_email.py`).

Lessons:

- Numeric prefixes provide ordering and are stable filenames
  irrespective of the slug.
- A slug that names the change makes the file self-describing.

We adapt this: migration filenames combine a target version and a
slug, e.g. `m_0_1_17_index_subfolder.py`. The `m_` prefix prevents the
module name from starting with a digit.

### chosen pattern

Single linear chain, target-version-keyed, target-version-ordered.
Each migration declares:

- `target_version: str` - the release that introduced the schema change
- `name: str` - short identifier (matches filename slug)
- `migrate(workspace: Path) -> MigrationResult`

The driver is one function: `run_pending_migrations(workspace)`. It
reads the manifest, parses both versions, filters the registry to
entries with `target_version > manifest.vaultspec_version`, runs them
in version order, then bumps the manifest version on success.

## constraints

- No mocks/patches/stubs/fakes/skips in tests. Real filesystem,
  `WorkspaceFactory` and `vaultspec_core.testing.synthetic` for
  fixtures.
- Migration must be idempotent: running it twice on the same workspace
  must be a no-op.
- A migration that raises must not bump the manifest version.
- The first migration must preserve the existing
  `_migrate_legacy_root_indexes` semantics: CRLF preservation, exact
  `#index` tag detection, atomic relocate.
- The `vault-fix` pre-commit hook must stop describing itself as
  performing migration.
- `spec doctor` JSON output must remain backwards-compatible: the new
  `migration_status` field is additive.
- No changes to consumer-facing behaviour beyond what the issue
  requires. Specifically, `vault check structure` (no `--fix`)
  continues to warn about misplaced indexes; only the mutation moves.

## open questions

None remaining. The registry design is fully determined by the issue
acceptance criteria and the prior-art analysis above. ADR follows.
