"""Related-link writes must never use attacker-controlled backup entries."""

from __future__ import annotations

import os
import stat
from typing import TYPE_CHECKING

import pytest

from ..related_surgery import (
    append_related_entry,
    atomic_write_restore,
    remove_related_entries,
)

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]

_ORIGINAL = b"---\r\nrelated:\r\n  - '[[gone]]'\r\n---\r\nBody.\r\n"
_OPERATOR = b"operator bytes that must never be overwritten\n"
_BACKUP_KINDS = (
    "regular",
    "hardlink",
    "absolute-symlink",
    "relative-symlink",
    "dangling-symlink",
    "directory",
)


def _plant_backup(backup: Path, target: Path, kind: str) -> bool:
    """Create a real obstacle, or assert that the OS refuses the link."""
    if kind == "regular":
        backup.write_bytes(_OPERATOR)
    elif kind == "directory":
        backup.mkdir()
        (backup / "occupant.txt").write_bytes(_OPERATOR)
    else:
        try:
            if kind == "hardlink":
                backup.hardlink_to(target)
            elif kind == "relative-symlink":
                backup.symlink_to(os.path.relpath(target, backup.parent))
            else:
                backup.symlink_to(target)
        except (OSError, NotImplementedError):
            assert not backup.exists()
            assert not backup.is_symlink()
            return False
    return True


@pytest.mark.parametrize("operation", ["append", "remove", "write"])
@pytest.mark.parametrize("kind", _BACKUP_KINDS)
def test_preexisting_backup_is_untouched(
    tmp_path: Path, operation: str, kind: str
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    doc = vault / "doc.md"
    doc.write_bytes(_ORIGINAL)
    target = tmp_path / "operator.txt"
    if kind != "dangling-symlink":
        target.write_bytes(_OPERATOR)
    backup = doc.with_suffix(".md.bak")
    if not _plant_backup(backup, target, kind):
        return
    before = backup.lstat()
    link_target = os.readlink(backup) if backup.is_symlink() else None

    if operation == "append":
        assert append_related_entry(doc, "[[new]]") is True
        assert b"[[new]]" in doc.read_bytes()
        assert b"[[gone]]" in doc.read_bytes()
    elif operation == "remove":
        assert remove_related_entries(doc, ["gone"]) == 1
        assert b"[[gone]]" not in doc.read_bytes()
    else:
        atomic_write_restore(doc, _ORIGINAL.decode("utf-8").replace("gone", "new"))
        assert doc.read_bytes() == _ORIGINAL.replace(b"gone", b"new")

    assert doc.read_bytes().endswith(b"---\r\nBody.\r\n")
    if kind == "dangling-symlink":
        assert not target.exists()
    else:
        assert target.read_bytes() == _OPERATOR
    after = backup.lstat()
    assert (after.st_dev, after.st_ino, after.st_mode) == (
        before.st_dev,
        before.st_ino,
        before.st_mode,
    )
    if link_target is not None:
        assert os.readlink(backup) == link_target
    if kind == "directory":
        assert (backup / "occupant.txt").read_bytes() == _OPERATOR
    elif kind != "dangling-symlink":
        assert backup.read_bytes() == _OPERATOR
    assert not list(vault.glob(".vs-write-*.tmp"))


def test_encoding_failure_preserves_document_and_backup(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_bytes(_ORIGINAL)
    target = tmp_path / "operator.txt"
    target.write_bytes(_OPERATOR)
    backup = doc.with_suffix(".md.bak")
    if not _plant_backup(backup, target, "hardlink"):
        return
    original_identity = doc.stat()

    with pytest.raises(UnicodeEncodeError):
        atomic_write_restore(doc, "unencodable high surrogate: \ud800")

    assert doc.read_bytes() == _ORIGINAL
    assert doc.stat().st_ino == original_identity.st_ino
    assert backup.samefile(target)
    assert target.read_bytes() == _OPERATOR
    assert not list(tmp_path.glob(".vs-write-*.tmp"))


def test_primary_symlink_is_refused_without_replacing_it(tmp_path: Path) -> None:
    target = tmp_path / "operator.txt"
    target.write_bytes(_OPERATOR)
    doc = tmp_path / "doc.md"
    if not _plant_backup(doc, target, "relative-symlink"):
        return
    link_target = os.readlink(doc)

    with pytest.raises(OSError, match="symbolic link"):
        atomic_write_restore(doc, "updated")

    assert doc.is_symlink()
    assert os.readlink(doc) == link_target
    assert target.read_bytes() == _OPERATOR
    assert not doc.with_suffix(".md.bak").exists()
    assert not list(tmp_path.glob(".vs-write-*.tmp"))


def test_missing_document_is_not_recreated_from_existing_backup(tmp_path: Path) -> None:
    doc = tmp_path / "missing.md"
    backup = doc.with_suffix(".md.bak")
    backup.write_bytes(_OPERATOR)

    with pytest.raises(FileNotFoundError):
        atomic_write_restore(doc, "updated")

    assert not doc.exists()
    assert backup.read_bytes() == _OPERATOR


def test_read_only_document_keeps_platform_write_semantics(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_bytes(_ORIGINAL)
    doc.chmod(stat.S_IREAD)
    try:
        if os.name == "nt":
            with pytest.raises(PermissionError) as caught:
                atomic_write_restore(doc, "updated")
            assert caught.value.filename == str(doc)
            assert doc.read_bytes() == _ORIGINAL
        else:
            atomic_write_restore(doc, "updated")
            assert doc.read_bytes() == b"updated"
        assert not stat.S_IMODE(doc.stat().st_mode) & stat.S_IWUSR
        assert not doc.with_suffix(".md.bak").exists()
        assert not list(tmp_path.glob(".vs-write-*.tmp"))
    finally:
        doc.chmod(stat.S_IREAD | stat.S_IWRITE)


def test_surrogateescaped_legacy_bytes_are_preserved(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_bytes(_ORIGINAL)

    atomic_write_restore(doc, "legacy byte: \udc80\r\n")

    assert doc.read_bytes() == b"legacy byte: \x80\r\n"
    assert not doc.with_suffix(".md.bak").exists()
