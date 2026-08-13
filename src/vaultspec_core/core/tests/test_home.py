"""Real-filesystem contracts for the machine-global Core home."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console

if TYPE_CHECKING:
    import pytest

from vaultspec_core.cli.spec_cmd_doctor import doctor_exit_code, render_diagnosis_table
from vaultspec_core.core import (
    ProcessRegistrySignal,
    core_home_layout,
    diagnose_process_registry,
)
from vaultspec_core.core.diagnosis import (
    FrameworkSignal,
    HomeDiagnosis,
    WorkspaceDiagnosis,
    diagnose,
)


def _write_record(path: Path, pid: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"name": path.stem, "pid": pid}), encoding="utf-8")


def test_core_home_reserves_process_and_nested_lease_directories(
    tmp_path: Path,
) -> None:
    layout = core_home_layout(tmp_path)

    assert layout.root == tmp_path
    assert layout.procs == tmp_path / "procs"
    assert layout.leases == tmp_path / "procs" / "leases"


def test_registry_probe_reports_live_process_and_ignores_opaque_artifacts(
    tmp_path: Path,
) -> None:
    layout = core_home_layout(tmp_path)
    _write_record(layout.procs / "worker-dev-local.json", os.getpid())
    (layout.procs / "future-schema.json").write_text("{}", encoding="utf-8")
    (layout.leases / "resource.lease").parent.mkdir(parents=True)
    (layout.leases / "resource.lease").write_text("opaque", encoding="utf-8")

    result = diagnose_process_registry(tmp_path)

    assert result.signal is ProcessRegistrySignal.HEALTHY
    assert result.record_count == 1
    assert result.stale_records == ()
    assert (layout.leases / "resource.lease").read_text(encoding="utf-8") == "opaque"


def test_dead_process_record_is_a_non_destructive_doctor_warning(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with subprocess.Popen([sys.executable, "-c", "pass"]) as process:
        dead_pid = process.pid
        assert process.wait(timeout=10) == 0
    layout = core_home_layout(tmp_path / "home")
    record = layout.procs / "gateway-dev-ended.json"
    _write_record(record, dead_pid)
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    result = diagnose_process_registry(layout.root)
    diagnosis = diagnose(workspace, core_home=layout.root)

    assert result.signal is ProcessRegistrySignal.STALE
    assert result.stale_records == (record.name,)
    assert diagnosis.process_registry.signal is ProcessRegistrySignal.STALE
    assert diagnosis.process_registry.stale_records == (record.name,)
    warning_only = WorkspaceDiagnosis(
        framework=FrameworkSignal.PRESENT,
        home=HomeDiagnosis(process_registry=diagnosis.process_registry),
    )
    # Machine-global residue is advisory and must not make an otherwise healthy
    # workspace fail its project-local doctor gate.
    assert doctor_exit_code(warning_only) == 0
    assert record.exists()

    console = Console(record=True, width=160)
    render_diagnosis_table(console, warning_only)
    rendered = capsys.readouterr().out
    assert "process registry" in rendered
    assert "gateway-dev-ended.json" in rendered
