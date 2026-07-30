"""Real CLI integration tests for explicit execution-record recovery.

Each case drives the live Typer application against on-disk plan and execution
records.  The assertions cover the public JSON and dry-run contract in addition
to reading back the actual metadata and historical body bytes.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from vaultspec_core.cli import app
from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory
from vaultspec_core.vaultcore import parse_vault_metadata

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.integration]

_PLAN_STEM = "2026-02-04-recovery-plan"


def _write_plan(root: Path, *, retired: str | None = None) -> Path:
    retired_ledger = f"\n<!-- RETIRED: {retired} -->" if retired else ""
    path = root / ".vault" / "plan" / f"{_PLAN_STEM}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        "tags:\n"
        "  - '#plan'\n"
        "  - '#recovery'\n"
        "date: '2026-02-04'\n"
        "modified: '2026-02-04'\n"
        "tier: L1\n"
        "related: []\n"
        "---\n\n"
        "# `recovery` plan\n\n"
        "## Steps\n\n"
        "- [ ] `S01` - recover evidence; `src/recovery.py`.\n"
        f"{retired_ledger}\n",
        encoding="utf-8",
    )
    return path


def _write_record(root: Path, step_id: str) -> Path:
    path = root / ".vault" / "exec" / "2026-02-04-recovery" / "record.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        (
            "---\r\n"
            "tags:\r\n"
            "  - '#exec'\r\n"
            "  - '#recovery'\r\n"
            "date: '2026-02-04'\r\n"
            "modified: '2026-02-04'\r\n"
            f"step_id: '{step_id}'\r\n"
            "related:\r\n"
            f"  - '[[{_PLAN_STEM}]]'\r\n"
            "---\r\n\r\n"
            "# Recovery record\r\n\r\n"
            "Historical evidence remains byte-for-byte.\r\n"
        ).encode()
    )
    return path


def _run(root: Path, *args: str):
    return CliRunner(env={"NO_COLOR": "1"}).invoke(
        app, ["vault", "exec", *args, "--target", str(root)]
    )


def _body(path: Path) -> bytes:
    return path.read_bytes().split(b"---\r\n", 2)[2]


def test_relink_dry_run_and_apply_emit_truthful_json_and_preserve_body(
    tmp_path: Path,
) -> None:
    WorkspaceFactory(tmp_path).install()
    _write_plan(tmp_path)
    record = _write_record(tmp_path, "P01.S01")
    before = record.read_bytes()

    preview = _run(
        tmp_path,
        "relink",
        "--record",
        str(record),
        "--step",
        "S01",
        "--dry-run",
        "--json",
    )

    assert preview.exit_code == 0, preview.output
    preview_data = json.loads(preview.output)
    assert preview_data["schema"] == "vaultspec.vault.exec.relink.v1"
    assert preview_data["status"] == "unchanged"
    assert preview_data["data"]["dry_run"] is True
    assert preview_data["data"]["changed"] is True
    assert record.read_bytes() == before

    applied = _run(
        tmp_path,
        "relink",
        "--record",
        str(record),
        "--step",
        "S01",
        "--json",
    )

    assert applied.exit_code == 0, applied.output
    applied_data = json.loads(applied.output)
    assert applied_data["status"] == "updated"
    assert applied_data["data"]["step_id"] == "S01"
    metadata, _ = parse_vault_metadata(record.read_text(encoding="utf-8"))
    assert metadata.step_id == "S01"
    assert _body(record) == before.split(b"---\r\n", 2)[2]


def test_detach_and_retire_apply_only_their_validated_recovery(tmp_path: Path) -> None:
    WorkspaceFactory(tmp_path).install()
    _write_plan(tmp_path, retired="S02")

    dangling = _write_record(tmp_path, "S99")
    body_before_detach = _body(dangling)
    detached = _run(tmp_path, "detach", "--record", str(dangling), "--json")

    assert detached.exit_code == 0, detached.output
    detached_data = json.loads(detached.output)
    assert detached_data["schema"] == "vaultspec.vault.exec.detach.v1"
    assert detached_data["status"] == "updated"
    assert detached_data["data"]["step_id"] is None
    metadata, _ = parse_vault_metadata(dangling.read_text(encoding="utf-8"))
    assert metadata.step_id is None
    assert _body(dangling) == body_before_detach

    retired = _write_record(tmp_path, "S02")
    retired_body = retired.read_bytes()
    retirement = _run(tmp_path, "retire", "--record", str(retired), "--json")

    assert retirement.exit_code == 0, retirement.output
    retirement_data = json.loads(retirement.output)
    assert retirement_data["schema"] == "vaultspec.vault.exec.retire.v1"
    assert retirement_data["status"] == "updated"
    archive_path = tmp_path / retirement_data["data"]["archive_path"]
    assert not retired.exists()
    assert archive_path.read_bytes() == retired_body
