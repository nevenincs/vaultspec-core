"""Real-PATH tests for absolute executable resolution before a subprocess launch."""

from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from vaultspec_core.core.helpers import require_executable

pytestmark = [pytest.mark.unit]


def _plant(directory: Path, name: str) -> Path:
    """Write an executable file named *name* into *directory* and return it."""
    directory.mkdir(parents=True, exist_ok=True)
    planted = directory / name
    planted.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    planted.chmod(planted.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return planted


def test_resolves_git_to_launchable_absolute_path() -> None:
    resolved = require_executable("git")

    assert Path(resolved).is_absolute()
    completed = subprocess.run(
        [resolved, "--version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    assert completed.stdout.startswith("git version")


def test_missing_program_raises_file_not_found_naming_it() -> None:
    with pytest.raises(FileNotFoundError) as info:
        require_executable("vaultspec-no-such-program")

    assert info.value.filename == "vaultspec-no-such-program"
    assert "not found on PATH" in str(info.value)


def test_windows_system_tool_resolves_from_the_system_directory() -> None:
    # Git for Windows puts a POSIX whoami ahead of the OS one on PATH.
    if sys.platform == "win32":
        resolved = Path(require_executable("whoami", windows_system=True))
        assert resolved.parent.name.lower() == "system32"
    else:
        assert Path(require_executable("whoami", windows_system=True)).is_absolute()


def test_program_in_the_working_directory_is_never_returned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GUARD: a workspace file named like the program must not be resolved.

    The working directory of these subprocesses is the workspace, which is
    content rather than configuration. Windows ``shutil.which`` searches the
    current directory ahead of every ``PATH`` entry, so a repository carrying a
    ``git.exe`` used to supply the ``git`` this helper exists to pin. The planted
    files are real and the chdir is real, so the lookup under test is the one
    that runs in production.
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    planted = {
        _plant(workspace, "git"),
        _plant(workspace, "git.exe"),
        _plant(workspace, "git.cmd"),
        _plant(workspace, "git.bat"),
    }
    monkeypatch.chdir(workspace)
    # Windows asks NeedCurrentDirectoryForExePath, which this variable turns off
    # for the whole machine. Clearing it holds the lookup to the default
    # configuration instead of to whatever this host happens to set.
    monkeypatch.delenv("NoDefaultCurrentDirectoryInExePath", raising=False)

    resolved = Path(require_executable("git")).resolve()

    # Compared after resolution: the pre-fix lookup answered with the relative
    # ``.\git.EXE``, which no comparison against an absolute path would catch.
    assert resolved not in {path.resolve() for path in planted}
    assert resolved.parent != workspace.resolve()
    assert Path(require_executable("git")).is_absolute()


def test_relative_path_entry_is_not_searched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GUARD: a relative PATH entry resolves against the working directory.

    POSIX ``shutil.which`` does not inject the current directory, but it does
    resolve a relative entry - and an empty one - against it, which reaches the
    same workspace file by a second route. ``PATH`` here holds nothing else, so
    a resolution can only have come from one of those entries. The ``.bat`` copy
    is what a Windows ``PATHEXT`` lookup finds, so the relative entry is a live
    route on both platforms.
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _plant(workspace / "tools", "vaultspec-planted-program")
    _plant(workspace / "tools", "vaultspec-planted-program.bat")
    monkeypatch.chdir(workspace)
    monkeypatch.setenv("PATH", os.pathsep.join(["", "tools", os.curdir]))

    with pytest.raises(FileNotFoundError) as info:
        require_executable("vaultspec-planted-program")

    assert info.value.filename == "vaultspec-planted-program"
