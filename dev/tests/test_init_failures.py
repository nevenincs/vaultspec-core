"""The init runner reports host failures instead of crashing on them."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from dev.exit_codes import INIT_STEP_FAILED
from dev.init.__main__ import _finish
from dev.init.contract import FAILED, Emitter, Step
from dev.init.process import run
from dev.init.stamp import report_path

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]


def test_an_executable_the_os_cannot_start_fails_the_step(tmp_path: Path) -> None:
    tool = tmp_path / "broken-tool.exe"
    tool.write_bytes(b"\x00not a program\x00")
    tool.chmod(0o755)

    result, code = run(
        Step(name="broken", argv=(str(tool),), summary="s"), cwd=tmp_path, echo=False
    )

    assert code == INIT_STEP_FAILED
    assert result.status == FAILED
    assert result.output_tail.startswith(f"{tool}: ")


def test_an_unwritable_report_path_is_announced_not_raised(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report_path(tmp_path).mkdir()

    _finish(tmp_path, {"remediation": []}, Emitter(json_mode=False), write_file=True)

    assert "could not write the report" in capsys.readouterr().err
