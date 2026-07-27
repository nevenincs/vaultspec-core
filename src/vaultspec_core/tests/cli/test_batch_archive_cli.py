"""Real CLI coverage for manifest-driven document archival."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from vaultspec_core.cli import app
from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.integration]


def _write_research(root: Path) -> Path:
    path = root / ".vault" / "research" / "2026-07-27-batch-archive-research.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        "tags:\n"
        "  - '#research'\n"
        "  - '#batch-archive'\n"
        "date: '2026-07-27'\n"
        "modified: '2026-07-27'\n"
        "related: []\n"
        "---\n\n"
        "# `batch-archive` research: `manifest recovery`\n\n"
        "## Findings\n\n"
        "The record is retained before it is archived.\n",
        encoding="utf-8",
    )
    return path


def _run(root: Path, manifest: Path, *args: str, command: str = "documents"):
    return CliRunner(env={"NO_COLOR": "1"}).invoke(
        app,
        [
            "vault",
            "archive",
            command,
            "--manifest",
            str(manifest),
            *args,
            "--target",
            str(root),
        ],
    )


def test_manifest_archive_dry_run_then_apply_uses_real_filesystem(
    tmp_path: Path,
) -> None:
    WorkspaceFactory(tmp_path).install()
    source = _write_research(tmp_path)
    manifest = tmp_path / "archive-manifest.txt"
    manifest.write_text(
        ".vault/research/2026-07-27-batch-archive-research.md\n",
        encoding="utf-8",
    )
    archive_path = (
        tmp_path
        / ".vault"
        / "_archive"
        / "research"
        / "2026-07-27-batch-archive-research.md"
    )

    preview = _run(tmp_path, manifest, "--dry-run", "--json")

    assert preview.exit_code == 0, preview.output
    preview_data = json.loads(preview.output)
    assert preview_data["schema"] == "vaultspec.vault.archive.documents.v1"
    assert preview_data["status"] == "unchanged"
    assert preview_data["data"]["dry_run"] is True
    assert preview_data["data"]["archived_count"] == 1
    assert preview_data["data"]["paths"] == [
        ".vault/_archive/research/2026-07-27-batch-archive-research.md"
    ]
    assert source.is_file()
    assert not archive_path.exists()

    applied = _run(tmp_path, manifest, "--json")

    assert applied.exit_code == 0, applied.output
    applied_data = json.loads(applied.output)
    assert applied_data["status"] == "updated"
    assert applied_data["data"]["dry_run"] is False
    assert not source.exists()
    assert archive_path.read_text(encoding="utf-8").endswith(
        "The record is retained before it is archived.\n"
    )


def test_manifest_restore_dry_run_then_apply_uses_real_filesystem(
    tmp_path: Path,
) -> None:
    WorkspaceFactory(tmp_path).install()
    archived = (
        tmp_path
        / ".vault"
        / "_archive"
        / "research"
        / "2026-07-27-batch-archive-research.md"
    )
    archived.parent.mkdir(parents=True)
    source = _write_research(tmp_path)
    archived.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    source.unlink()
    live_path = tmp_path / ".vault" / "research" / archived.name
    manifest = tmp_path / "restore-manifest.txt"
    manifest.write_text(
        ".vault/_archive/research/2026-07-27-batch-archive-research.md\n",
        encoding="utf-8",
    )

    preview = _run(tmp_path, manifest, "--dry-run", "--json", command="restore")

    assert preview.exit_code == 0, preview.output
    preview_data = json.loads(preview.output)
    assert preview_data["schema"] == "vaultspec.vault.archive.restore.v1"
    assert preview_data["status"] == "unchanged"
    assert preview_data["data"] == {
        "status": "unchanged",
        "restored_count": 1,
        "paths": [".vault/research/2026-07-27-batch-archive-research.md"],
        "deduplicated_count": 0,
        "deduplicated_paths": [],
        "cross_link_paths": [],
        "dry_run": True,
    }
    assert archived.is_file()
    assert not live_path.exists()

    applied = _run(tmp_path, manifest, "--json", command="restore")

    assert applied.exit_code == 0, applied.output
    applied_data = json.loads(applied.output)
    assert applied_data["schema"] == "vaultspec.vault.archive.restore.v1"
    assert applied_data["status"] == "updated"
    assert applied_data["data"]["dry_run"] is False
    assert applied_data["data"]["restored_count"] == 1
    assert not archived.exists()
    assert live_path.read_text(encoding="utf-8").endswith(
        "The record is retained before it is archived.\n"
    )


def test_restore_json_error_is_parseable_and_does_not_move_the_source(
    tmp_path: Path,
) -> None:
    WorkspaceFactory(tmp_path).install()
    archived = (
        tmp_path
        / ".vault"
        / "_archive"
        / "research"
        / "2026-07-27-batch-archive-research.md"
    )
    archived.parent.mkdir(parents=True)
    source = _write_research(tmp_path)
    archived.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    manifest = tmp_path / "restore-manifest.txt"
    manifest.write_text(
        ".vault/_archive/research/2026-07-27-batch-archive-research.md\n",
        encoding="utf-8",
    )

    result = _run(tmp_path, manifest, "--json", command="restore")

    assert result.exit_code == 1
    data = json.loads(result.output)
    assert data["schema"] == "vaultspec.error.v1"
    assert data["status"] == "failed"
    assert "destination already exists" in data["data"]["message"]
    assert archived.is_file()

    deduplicated = _run(
        tmp_path,
        manifest,
        "--deduplicate-identical",
        "--json",
        command="restore",
    )

    assert deduplicated.exit_code == 0, deduplicated.output
    deduplicated_data = json.loads(deduplicated.output)
    assert deduplicated_data["schema"] == "vaultspec.vault.archive.restore.v1"
    assert deduplicated_data["data"]["restored_count"] == 0
    assert deduplicated_data["data"]["deduplicated_count"] == 1
    assert deduplicated_data["data"]["deduplicated_paths"] == [
        ".vault/_archive/research/2026-07-27-batch-archive-research.md"
    ]
    assert not archived.exists()
