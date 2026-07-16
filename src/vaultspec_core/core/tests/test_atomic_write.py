"""Real-filesystem integrity tests for shared atomic file replacement."""

from __future__ import annotations

import os
import stat
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.core.helpers import atomic_write

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]


def _legacy_temp(path: Path) -> Path:
    return path.with_suffix(path.suffix + f".{os.getpid()}.tmp")


class TestAtomicWriteNamespace:
    def test_regular_legacy_temp_is_untouched(self, tmp_path: Path) -> None:
        destination = tmp_path / "regular.md"
        obstacle = _legacy_temp(destination)
        obstacle.write_bytes(b"operator bytes\n")

        atomic_write(destination, "managed")

        assert destination.read_bytes() == b"managed"
        assert obstacle.read_bytes() == b"operator bytes\n"

    def test_relative_link_legacy_temp_is_untouched(self, tmp_path: Path) -> None:
        destination = tmp_path / "relative.md"
        operator = tmp_path / "operator.txt"
        operator.write_bytes(b"operator bytes\n")
        obstacle = _legacy_temp(destination)
        obstacle.symlink_to(operator.name)

        atomic_write(destination, "managed")

        assert destination.read_bytes() == b"managed"
        assert obstacle.is_symlink()
        assert os.readlink(obstacle) == operator.name
        assert operator.read_bytes() == b"operator bytes\n"

    def test_broken_link_legacy_temp_is_untouched(self, tmp_path: Path) -> None:
        destination = tmp_path / "broken.md"
        obstacle = _legacy_temp(destination)
        obstacle.symlink_to("missing-operator.txt")

        atomic_write(destination, "managed")

        assert destination.read_bytes() == b"managed"
        assert obstacle.is_symlink()
        assert os.readlink(obstacle) == "missing-operator.txt"

    def test_directory_legacy_temp_is_untouched(self, tmp_path: Path) -> None:
        destination = tmp_path / "directory.md"
        obstacle = _legacy_temp(destination)
        obstacle.mkdir()
        (obstacle / "operator.txt").write_bytes(b"operator bytes\n")

        atomic_write(destination, "managed")

        assert destination.read_bytes() == b"managed"
        assert obstacle.is_dir()
        assert (obstacle / "operator.txt").read_bytes() == b"operator bytes\n"


class TestAtomicWriteDestination:
    def test_preserves_existing_regular_file_mode(self, tmp_path: Path) -> None:
        destination = tmp_path / "mode.md"
        destination.write_text("old", encoding="utf-8")
        destination.chmod(0o640)

        atomic_write(destination, "new")

        assert destination.read_text(encoding="utf-8") == "new"
        if os.name != "nt":
            assert stat.S_IMODE(destination.stat().st_mode) == 0o640

    def test_replaces_relative_link_without_writing_target(
        self, tmp_path: Path
    ) -> None:
        operator = tmp_path / "operator-target.md"
        operator.write_bytes(b"operator bytes\n")
        destination = tmp_path / "linked.md"
        destination.symlink_to(operator.name)

        atomic_write(destination, "managed")

        assert not destination.is_symlink()
        assert destination.read_bytes() == b"managed"
        assert operator.read_bytes() == b"operator bytes\n"

    def test_replaces_broken_link(self, tmp_path: Path) -> None:
        destination = tmp_path / "broken-destination.md"
        destination.symlink_to("missing-target.md")

        atomic_write(destination, "managed")

        assert not destination.is_symlink()
        assert destination.read_bytes() == b"managed"

    def test_directory_failure_preserves_topology(self, tmp_path: Path) -> None:
        destination = tmp_path / "destination.md"
        destination.mkdir()
        (destination / "operator.txt").write_bytes(b"operator bytes\n")

        with pytest.raises(OSError):
            atomic_write(destination, "managed")

        assert destination.is_dir()
        assert (destination / "operator.txt").read_bytes() == b"operator bytes\n"
        assert not list(tmp_path.glob(".vs-write-*.tmp"))

    def test_missing_parent_fails_without_creating_ancestors(
        self, tmp_path: Path
    ) -> None:
        parent = tmp_path / "missing"

        with pytest.raises(FileNotFoundError):
            atomic_write(parent / "destination.md", "managed")

        assert not parent.exists()

    def test_long_destination_component_uses_short_temp_name(
        self, tmp_path: Path
    ) -> None:
        destination = tmp_path / ("d" * 230 + ".md")

        atomic_write(destination, "managed")

        assert destination.read_bytes() == b"managed"
