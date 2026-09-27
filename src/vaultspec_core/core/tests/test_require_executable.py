"""Real-PATH tests for absolute executable resolution before a subprocess launch."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from vaultspec_core.core.helpers import require_executable

pytestmark = [pytest.mark.unit]


def test_resolves_real_program_to_launchable_absolute_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    interpreter = Path(sys.executable)
    monkeypatch.setenv("PATH", str(interpreter.parent))

    resolved = require_executable(interpreter.stem)

    assert Path(resolved).is_absolute()
    assert Path(resolved).samefile(interpreter)
    completed = subprocess.run(
        [resolved, "-c", "print('ok')"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    assert completed.stdout.strip() == "ok"


def test_missing_program_raises_file_not_found_naming_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))

    with pytest.raises(FileNotFoundError) as info:
        require_executable("vaultspec-no-such-program")

    assert info.value.filename == "vaultspec-no-such-program"
    assert "not found on PATH" in str(info.value)


def test_windows_system_tool_ignores_path_shadowing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # A PATH holding only an unrelated directory must not stop an OS tool from
    # resolving on Windows, and the flag must be inert elsewhere.
    monkeypatch.setenv("PATH", str(tmp_path))

    if sys.platform == "win32":
        resolved = Path(require_executable("icacls", windows_system=True))
        assert resolved.parent.name.lower() == "system32"
    else:
        with pytest.raises(FileNotFoundError):
            require_executable("icacls", windows_system=True)
