"""Real-filesystem integrity tests for shared atomic file replacement."""

from __future__ import annotations

import contextlib
import os
import stat
import time
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.core.helpers import atomic_write

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]


def _legacy_temp(path: Path) -> Path:
    return path.with_suffix(path.suffix + f".{os.getpid()}.tmp")


def _plant_symlink(link: Path, target: str) -> bool:
    """Plant a real OS symlink, or prove this host refuses symlink creation.

    Windows refuses symlink creation without developer mode or elevation; on
    such a host the symlinked-obstacle scenario these tests model cannot exist,
    so the refusal itself is the asserted behavior and the caller ends its
    scenario early. On every capable host (Linux CI, Windows with developer
    mode) the symlink is real and the full scenario runs. Mirrors the
    ``_plant_symlink`` idiom in ``test_rename_feature_security`` - a real OS
    probe, never a runtime skip.

    Returns:
        ``True`` when the symlink was created, ``False`` when the OS refused.
    """
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        assert not link.exists(), "refused symlink left an artifact behind"
        return False
    assert link.is_symlink()
    return True


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
        if not _plant_symlink(obstacle, operator.name):
            return

        atomic_write(destination, "managed")

        assert destination.read_bytes() == b"managed"
        assert obstacle.is_symlink()
        assert os.readlink(obstacle) == operator.name
        assert operator.read_bytes() == b"operator bytes\n"

    def test_broken_link_legacy_temp_is_untouched(self, tmp_path: Path) -> None:
        destination = tmp_path / "broken.md"
        obstacle = _legacy_temp(destination)
        if not _plant_symlink(obstacle, "missing-operator.txt"):
            return

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
        if not _plant_symlink(destination, operator.name):
            return

        atomic_write(destination, "managed")

        assert not destination.is_symlink()
        assert destination.read_bytes() == b"managed"
        assert operator.read_bytes() == b"operator bytes\n"

    def test_replaces_broken_link(self, tmp_path: Path) -> None:
        destination = tmp_path / "broken-destination.md"
        if not _plant_symlink(destination, "missing-target.md"):
            return

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


class TestAtomicWriteReadOnlyDestination:
    """A read-only destination must not cost a leaked temporary (issue #412).

    The destination's mode used to be stamped onto the temporary *before* the
    replace, which made the temporary read-only too, so the cleanup unlink in
    the ``finally`` failed and the file survived the run. What surfaced named
    that temporary rather than the file the caller asked to write.

    Whether the write itself succeeds is platform behaviour and these tests do
    not force it either way: on POSIX the directory's write permission governs
    the rename, so it succeeds; on Windows a read-only destination refuses
    ``MoveFileEx`` outright. Both are asserted below, and neither may leak.
    """

    @staticmethod
    def _read_only_destination(tmp_path: Path) -> Path:
        destination = tmp_path / "read-only.md"
        destination.write_bytes(b"operator bytes\n")
        destination.chmod(stat.S_IREAD)
        return destination

    def test_leaves_no_temporary_behind(self, tmp_path: Path) -> None:
        destination = self._read_only_destination(tmp_path)

        with contextlib.suppress(PermissionError):
            atomic_write(destination, "managed")

        assert not list(tmp_path.glob(".vs-write-*.tmp"))

    def test_windows_refusal_names_the_destination(self, tmp_path: Path) -> None:
        """The reported path is the file the caller named, not a temporary.

        On POSIX the write succeeds, so there is no refusal to name; the
        assertion there is that the operator's mode survived the replace.
        """
        destination = self._read_only_destination(tmp_path)

        if os.name == "nt":
            with pytest.raises(PermissionError) as caught:
                atomic_write(destination, "managed")

            assert caught.value.filename == str(destination)
            assert ".vs-write-" not in str(caught.value.filename)
            assert destination.read_bytes() == b"operator bytes\n"
        else:
            atomic_write(destination, "managed")

            assert destination.read_bytes() == b"managed"
            assert not stat.S_IMODE(destination.stat().st_mode) & stat.S_IWUSR

    def test_refusal_is_immediate_not_after_the_retry_budget(
        self, tmp_path: Path
    ) -> None:
        """A read-only destination is permanent, so it must not be retried.

        ``ERROR_ACCESS_DENIED`` is also how the transient scanner race reports
        itself, so this condition used to spend the whole Windows retry budget
        before failing at something that was never going to clear.
        """
        from vaultspec_core.core.helpers import (
            _WINDOWS_REPLACE_RETRY_BUDGET_SECONDS,
        )

        destination = self._read_only_destination(tmp_path)

        started = time.monotonic()
        with contextlib.suppress(PermissionError):
            atomic_write(destination, "managed")
        elapsed = time.monotonic() - started

        assert elapsed < _WINDOWS_REPLACE_RETRY_BUDGET_SECONDS

    def test_a_writable_destination_still_round_trips(self, tmp_path: Path) -> None:
        """The read-only guard must not refuse an ordinary write."""
        destination = tmp_path / "writable.md"
        destination.write_bytes(b"old\n")

        atomic_write(destination, "new")

        assert destination.read_bytes() == b"new"
        assert not list(tmp_path.glob(".vs-write-*.tmp"))
