"""Real-PATH tests for absolute executable resolution before a subprocess launch."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from vaultspec_core.core.helpers import require_executable

pytestmark = [pytest.mark.unit]


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
