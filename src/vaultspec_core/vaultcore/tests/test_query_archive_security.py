"""Feature archival rejects linked trees before discovery or mutation."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.config import reset_config
from vaultspec_core.core.exceptions import VaultSpecError
from vaultspec_core.vaultcore.query import archive_feature, unarchive_feature

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _reset_config() -> Iterator[None]:
    reset_config()
    yield
    reset_config()


def _write(path: Path, *, feature: str = "feat") -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = f"---\ntags: [adr, {feature}]\n---\nEvidence: café\n".encode()
    path.write_bytes(content)
    return content


def _link(target: Path, link: Path, kind: str) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    if kind == "junction":
        if os.name != "nt":
            pytest.skip("junctions are Windows-only")
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            check=True,
            capture_output=True,
        )
        assert link.is_junction()
    else:
        os.symlink(target, link, target_is_directory=True)
        assert link.is_symlink()


@pytest.mark.parametrize("kind", ["symlink", "junction"])
@pytest.mark.parametrize("dry_run", [False, True])
@pytest.mark.parametrize("operation", ["archive", "unarchive"])
@pytest.mark.parametrize(
    "location", ["vault", "archive", "source", "destination", "runtime"]
)
def test_rejects_linked_managed_trees_without_touching_targets(
    tmp_path: Path, kind: str, dry_run: bool, operation: str, location: str
) -> None:
    root = tmp_path / "project"
    vault = root / ".vault"
    external = tmp_path / "external"
    external.mkdir()
    source_relative = (
        Path("adr/doc.md") if operation == "archive" else Path("_archive/adr/doc.md")
    )
    destination_relative = (
        Path("_archive/adr/doc.md") if operation == "archive" else Path("adr/doc.md")
    )
    source = vault / source_relative
    content = _write(source)
    # A second matching document proves unsafe batches do not partly apply.
    control = vault / source_relative.parent.parent / "plan/control.md"
    control_content = _write(control)
    if location == "vault":
        source.unlink()
        control.unlink()
        source.parent.rmdir()
        control.parent.rmdir()
        if operation == "unarchive":
            (vault / "_archive").rmdir()
        vault.rmdir()
        _write(external / source_relative)
        _link(external, vault, kind)
    elif location == "source":
        source.unlink()
        source.parent.rmdir()
        _write(external / "doc.md")
        _link(external, source.parent, kind)
    elif location == "archive":
        if operation == "unarchive":
            source.unlink()
            control.unlink()
            source.parent.rmdir()
            control.parent.rmdir()
            (vault / "_archive").rmdir()
            _write(external / "adr/doc.md")
            _write(external / "plan/control.md")
        _link(external, vault / "_archive", kind)
    elif location == "destination":
        _link(external, (vault / destination_relative).parent, kind)
    else:
        _link(external, vault / "data", kind)
    before = {
        p.relative_to(external): p.read_bytes()
        for p in external.rglob("*")
        if p.is_file()
    }

    action = archive_feature if operation == "archive" else unarchive_feature
    with pytest.raises(VaultSpecError):
        action(root, "feat", dry_run=dry_run)

    assert source.read_bytes() == content
    if location != "vault":
        assert control.read_bytes() == control_content
    assert {
        p.relative_to(external): p.read_bytes()
        for p in external.rglob("*")
        if p.is_file()
    } == before
    assert not (external / ".vault.lock").exists()
    assert not (vault / destination_relative).exists()


@pytest.mark.parametrize("operation", ["archive", "unarchive"])
@pytest.mark.parametrize("dry_run", [False, True])
def test_collision_refuses_the_whole_feature_batch(
    tmp_path: Path, operation: str, dry_run: bool
) -> None:
    prefix = ".vault" if operation == "archive" else ".vault/_archive"
    dest_prefix = ".vault/_archive" if operation == "archive" else ".vault"
    first = tmp_path / prefix / "adr/first.md"
    second = tmp_path / prefix / "plan/second.md"
    first_bytes = _write(first)
    second_bytes = _write(second)
    collision = tmp_path / dest_prefix / "plan/second.md"
    collision_bytes = _write(collision, feature="other")

    action = archive_feature if operation == "archive" else unarchive_feature
    with pytest.raises(VaultSpecError, match="destination already exists"):
        action(tmp_path, "feat", dry_run=dry_run)

    assert first.read_bytes() == first_bytes
    assert second.read_bytes() == second_bytes
    assert collision.read_bytes() == collision_bytes
    assert not (tmp_path / dest_prefix / "adr/first.md").exists()


def test_feature_round_trip_preserves_paths_bytes_and_dry_run(tmp_path: Path) -> None:
    source = tmp_path / ".vault/adr/nested/doc.md"
    content = _write(source)
    untouched = tmp_path / ".vault/plan/other.md"
    other_content = _write(untouched, feature="other")
    archive = tmp_path / ".vault/_archive/adr/nested/doc.md"

    preview = archive_feature(tmp_path, " #feat ", dry_run=True)
    assert preview["paths"] == [str(archive.relative_to(tmp_path))]
    assert preview["archived_count"] == 1
    assert not archive.exists()
    assert source.read_bytes() == content
    result = archive_feature(tmp_path, "feat")
    assert result["paths"] == preview["paths"]
    assert archive.read_bytes() == content
    assert not source.exists()

    preview_restore = unarchive_feature(tmp_path, " #feat ", dry_run=True)
    assert preview_restore == {
        "unarchived_count": 1,
        "paths": [str(source.relative_to(tmp_path))],
        "dry_run": True,
    }
    assert archive.read_bytes() == content
    restored = unarchive_feature(tmp_path, "feat")
    assert restored["paths"] == preview_restore["paths"]
    assert source.read_bytes() == content
    assert untouched.read_bytes() == other_content
    assert not (tmp_path / ".vault/_archive").exists()


@pytest.mark.parametrize("operation", [archive_feature, unarchive_feature])
def test_missing_vault_keeps_the_zero_match_error(
    tmp_path: Path, operation: Callable[[Path, str], object]
) -> None:
    with pytest.raises(VaultSpecError, match="matches zero"):
        operation(tmp_path, "feat")


@pytest.mark.parametrize("kind", ["symlink", "junction"])
@pytest.mark.parametrize("operation", [archive_feature, unarchive_feature])
def test_rejects_internal_links_even_when_resolved_paths_stay_in_vault(
    tmp_path: Path, kind: str, operation: Callable[[Path, str], object]
) -> None:
    vault = tmp_path / ".vault"
    prefix = vault if operation is archive_feature else vault / "_archive"
    real = prefix / "research"
    content = _write(real / "doc.md")
    _link(real, prefix / "adr", kind)
    with pytest.raises(VaultSpecError, match="symlink or junction"):
        operation(tmp_path, "feat")
    assert (real / "doc.md").read_bytes() == content


@pytest.mark.parametrize("operation", [archive_feature, unarchive_feature])
def test_rejects_dangling_markdown_links(
    tmp_path: Path, operation: Callable[[Path, str], object]
) -> None:
    prefix = ".vault" if operation is archive_feature else ".vault/_archive"
    link = tmp_path / prefix / "adr/doc.md"
    link.parent.mkdir(parents=True)
    os.symlink(tmp_path / "missing.md", link)
    with pytest.raises(VaultSpecError, match="symlink"):
        operation(tmp_path, "feat")
    assert link.is_symlink()


@pytest.mark.parametrize("kind", ["symlink", "junction"])
@pytest.mark.parametrize("operation", [archive_feature, unarchive_feature])
def test_rejects_linked_configured_vault_ancestors_inside_project(
    tmp_path: Path,
    kind: str,
    operation: Callable[[Path, str], object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    relative = (
        "vault/adr/doc.md"
        if operation is archive_feature
        else "vault/_archive/adr/doc.md"
    )
    target = tmp_path / "real"
    source = target / relative
    content = _write(source)
    _link(target, tmp_path / "alias", kind)
    monkeypatch.setenv("VAULTSPEC_DOCS_DIR", "alias/vault")
    reset_config()
    with pytest.raises(VaultSpecError, match="symlink or junction"):
        operation(tmp_path, "feat")
    assert source.read_bytes() == content


@pytest.mark.parametrize("kind", ["symlink", "junction"])
def test_restore_cleanup_does_not_descend_into_excluded_linked_directories(
    tmp_path: Path, kind: str
) -> None:
    root = tmp_path / "project"
    source = root / ".vault/_archive/adr/doc.md"
    content = _write(source)
    external = tmp_path / "external"
    empty_child = external / "empty"
    empty_child.mkdir(parents=True)
    link = root / ".vault/_archive/.obsidian"
    _link(external, link, kind)

    result = unarchive_feature(root, "feat")

    assert result["unarchived_count"] == 1
    assert (root / ".vault/adr/doc.md").read_bytes() == content
    assert empty_child.is_dir()
    assert link.is_symlink() or link.is_junction()
