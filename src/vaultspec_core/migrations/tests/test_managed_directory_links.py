"""Migration preflight refuses external sources and redirected destinations."""

from __future__ import annotations

import importlib
import os
import subprocess
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.config import reset_config
from vaultspec_core.migrations import MigrationError, run_pending_migrations
from vaultspec_core.migrations._paths import check_path, check_tree

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

pytestmark = pytest.mark.unit

_DOC_MIGRATIONS = (
    "m_0_1_17_index_subfolder",
    "m_0_1_29_modified_stamp_backfill",
    "m_0_1_55_body_hash_seed",
    "m_0_1_58_exec_ledger_fold",
    "m_0_1_74_exec_ledger_only",
)


@pytest.fixture(autouse=True)
def reset_cfg() -> Generator[None]:
    reset_config()
    yield
    reset_config()


def _link(link: Path, target: Path, *, directory: bool = True) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(target, target_is_directory=directory)


@pytest.mark.parametrize("module", _DOC_MIGRATIONS)
@pytest.mark.parametrize("relative", (".vault", ".vault/exec", ".vault/exec/demo"))
def test_document_migrations_reject_linked_directories(
    tmp_path: Path, module: str, relative: str
) -> None:
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    outside.mkdir()
    record = outside / "legacy.index.md"
    payload = b"---\nstep_id: S1\nbody_schema: body-v1\n---\n## Scope\n- `secret`\n"
    record.write_bytes(payload)
    link = workspace / relative
    _link(link, outside)
    migration = importlib.import_module(f"vaultspec_core.migrations.{module}")

    with pytest.raises(MigrationError, match="linked path"):
        migration.migrate(workspace)
    if hasattr(migration, "preview"):
        with pytest.raises(MigrationError, match="linked path"):
            migration.preview(workspace)

    assert link.is_symlink()
    assert record.read_bytes() == payload
    assert sorted(path.name for path in outside.iterdir()) == [record.name]
    assert not (workspace / ".vault" / ".trash").exists()


@pytest.mark.parametrize(
    "relative",
    (
        ".vaultspec",
        ".vaultspec/rules",
        ".vaultspec/rules/skills",
        ".vaultspec/rules/skills/nested",
        ".vaultspec/skills",
        ".vaultspec/skills/nested",
        ".vaultspec/__framework_flatten_tmp__",
    ),
)
def test_flatten_rejects_links_before_collision_merge(
    tmp_path: Path, relative: str
) -> None:
    from vaultspec_core.migrations.m_0_1_35_framework_flatten import migrate

    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    outside.mkdir()
    precious = outside / "precious.md"
    precious.write_bytes(b"outside bytes")
    link = workspace / relative
    _link(link, outside)
    # Build both halves of a merge only where they do not traverse the link.
    if relative not in (".vaultspec", ".vaultspec/rules"):
        (workspace / ".vaultspec/rules/rules").mkdir(parents=True)
    if not relative.startswith(".vaultspec/rules") and relative != ".vaultspec":
        source = workspace / ".vaultspec/rules/skills/nested"
        source.mkdir(parents=True)
        (source / "precious.md").write_bytes(b"replacement")

    with pytest.raises(MigrationError, match="linked path"):
        migrate(workspace)

    assert precious.read_bytes() == b"outside bytes"
    assert link.is_symlink()
    assert sorted(path.name for path in outside.iterdir()) == [precious.name]


@pytest.mark.parametrize(
    ("module", "relative"),
    (
        ("m_0_1_20_gitignore_reversal", ".vaultspec/rules/rules"),
        ("m_0_1_24_codex_agents_dedup", ".codex"),
        ("m_0_2_4_trigger_split", ".vaultspec/hooks"),
        ("m_0_2_4_trigger_split", ".vaultspec/triggers"),
        ("m_0_1_17_index_subfolder", ".vault/index"),
        ("m_0_1_17_index_subfolder", ".vault/.trash"),
        ("m_0_1_58_exec_ledger_fold", ".vault/.trash"),
        ("m_0_1_74_exec_ledger_only", ".vault/.trash"),
        ("m_0_1_58_exec_ledger_fold", ".vaultspec/templates"),
        ("m_0_1_74_exec_ledger_only", ".vaultspec/templates"),
    ),
)
def test_auxiliary_sources_and_destinations_are_checked(
    tmp_path: Path, module: str, relative: str
) -> None:
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    outside.mkdir()
    _link(workspace / relative, outside)
    (workspace / ".vault/exec").mkdir(parents=True, exist_ok=True)
    migration = importlib.import_module(f"vaultspec_core.migrations.{module}")

    with pytest.raises(MigrationError, match="linked path"):
        migration.migrate(workspace)

    assert not list(outside.iterdir())


@pytest.mark.parametrize("module", _DOC_MIGRATIONS[1:])
def test_linked_document_is_never_read_or_snapshotted(
    tmp_path: Path, module: str
) -> None:
    workspace = tmp_path / "workspace"
    secret = tmp_path / "secret.md"
    secret.write_bytes(b"external document")
    _link(workspace / ".vault/exec/demo/record.md", secret, directory=False)
    migration = importlib.import_module(f"vaultspec_core.migrations.{module}")

    with pytest.raises(MigrationError, match="linked path"):
        migration.migrate(workspace)

    assert secret.read_bytes() == b"external document"
    assert not (workspace / ".vault/.trash").exists()


def test_dangling_and_internal_directory_links_are_rejected(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _link(workspace / "dangling", tmp_path / "missing")
    with pytest.raises(MigrationError, match="linked path"):
        check_tree(workspace, workspace / "dangling")
    (workspace / "real").mkdir()
    _link(workspace / "alias", workspace / "real")
    with pytest.raises(MigrationError, match="linked path"):
        check_tree(workspace, workspace / "alias")


def test_workspace_alias_and_missing_destinations_remain_valid(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    alias = tmp_path / "alias"
    _link(alias, workspace)
    check_tree(alias, alias / ".vault")
    check_path(alias, alias / ".vault/index/new.md")
    with pytest.raises(MigrationError, match="escapes workspace"):
        check_path(alias, alias / "../outside/new.md")


def test_driver_rejects_redirected_manifest_before_locking(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    _link(tmp_path / "workspace/.vaultspec", outside)
    with pytest.raises(MigrationError, match="linked path"):
        run_pending_migrations(tmp_path / "workspace", use_cache=False)
    assert not list(outside.iterdir())


def test_driver_rejects_dangling_lock_link(tmp_path: Path) -> None:
    from vaultspec_core.core.manifest import MANIFEST_FILENAME, write_manifest

    workspace = tmp_path / "workspace"
    (workspace / ".vaultspec").mkdir(parents=True)
    write_manifest(workspace, set())
    manifest = workspace / ".vaultspec" / MANIFEST_FILENAME
    outside = tmp_path / "not-created.lock"
    lock = manifest.with_suffix(manifest.suffix + ".lock")
    lock.unlink(missing_ok=True)
    _link(lock, outside, directory=False)
    with pytest.raises(MigrationError, match="linked path"):
        run_pending_migrations(workspace, registry=[], use_cache=False)
    assert not outside.exists()


@pytest.mark.parametrize(
    ("module", "relative"),
    (
        ("m_0_1_20_gitignore_reversal", ".gitignore.lock"),
        ("m_0_1_58_exec_ledger_fold", ".vault/data/.vault.lock"),
        ("m_0_1_74_exec_ledger_only", ".vault/data/.vault.lock"),
    ),
)
def test_migration_lock_links_cannot_create_outside_files(
    tmp_path: Path, module: str, relative: str
) -> None:
    workspace = tmp_path / "workspace"
    outside = tmp_path / "not-created.lock"
    _link(workspace / relative, outside, directory=False)
    migration = importlib.import_module(f"vaultspec_core.migrations.{module}")
    with pytest.raises(MigrationError, match="linked path"):
        migration.migrate(workspace)
    assert not outside.exists()


@pytest.mark.parametrize("module", _DOC_MIGRATIONS)
@pytest.mark.parametrize("excluded", (".obsidian", "_archive"))
def test_excluded_content_does_not_block_migration(
    tmp_path: Path, module: str, excluded: str
) -> None:
    workspace = tmp_path / "workspace"
    secret = tmp_path / "external.md"
    secret.write_bytes(b"editor or archived content")
    _link(workspace / ".vault" / excluded / "plugin.js", secret, directory=False)
    migration = importlib.import_module(f"vaultspec_core.migrations.{module}")
    migration.migrate(workspace)
    assert secret.read_bytes() == b"editor or archived content"


@pytest.mark.skipif(os.name != "nt", reason="Windows junction boundary")
def test_windows_junction_is_rejected(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    junction = workspace / ".vault"
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(outside)],
        check=True,
        capture_output=True,
    )
    try:
        with pytest.raises(MigrationError, match="linked path"):
            check_tree(workspace, junction)
        assert not list(outside.iterdir())
    finally:
        junction.rmdir()
