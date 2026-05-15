"""Tests for the ``vaultspec-core vault repair`` operator pipeline."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.cli import app

if TYPE_CHECKING:
    from pathlib import Path

    from typer.testing import CliRunner

    from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory

pytestmark = [pytest.mark.unit]


def _write_doc(root: Path, doc_type: str, stem: str, feature: str) -> Path:
    path = root / ".vault" / doc_type / f"{stem}-{doc_type}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        "tags:\n"
        f"  - '#{doc_type}'\n"
        f"  - '#{feature}'\n"
        "date: '2026-05-15'\n"
        "related: []\n"
        "---\n"
        f"\n# {stem}\n",
        encoding="utf-8",
    )
    return path


def _json_payload(output: str) -> dict:
    start = output.index("{")
    return json.loads(output[start:])


class TestVaultRepair:
    def test_help_lists_repair_command(
        self,
        factory: WorkspaceFactory,
        runner: CliRunner,
    ) -> None:
        factory.install("core")

        result = runner.invoke(app, ["--target", str(factory.path), "vault", "--help"])

        assert result.exit_code == 0
        assert "repair" in result.output

    def test_dry_run_reports_index_plan_without_writing(
        self,
        factory: WorkspaceFactory,
    ) -> None:
        factory.install("core")
        _write_doc(
            factory.path,
            "research",
            "2026-05-15-repair-dry-run",
            "repair-dry-run",
        )
        index_path = factory.path / ".vault" / "index" / "repair-dry-run.index.md"

        result = factory.run(
            "vault",
            "repair",
            "--feature",
            "repair-dry-run",
            "--dry-run",
            "--json",
        )
        payload = _json_payload(result.output)

        assert result.exit_code == 0
        assert payload["dry_run"] is True
        assert payload["changed_files"] == []
        assert ".vault/index/repair-dry-run.index.md" in payload["generated_indexes"]
        assert not index_path.exists()

    def test_repair_refreshes_feature_index(
        self,
        factory: WorkspaceFactory,
    ) -> None:
        factory.install("core")
        _write_doc(
            factory.path,
            "research",
            "2026-05-15-repair-index",
            "repair-index",
        )
        index_path = factory.path / ".vault" / "index" / "repair-index.index.md"

        result = factory.run(
            "vault",
            "repair",
            "--feature",
            "repair-index",
            "--json",
        )
        payload = _json_payload(result.output)

        assert result.exit_code == 0
        assert index_path.exists()
        assert ".vault/index/repair-index.index.md" in payload["generated_indexes"]
        assert ".vault/index/repair-index.index.md" in payload["changed_files"]

    def test_no_index_skips_generated_artifact_refresh(
        self,
        factory: WorkspaceFactory,
    ) -> None:
        factory.install("core")
        _write_doc(
            factory.path,
            "research",
            "2026-05-15-repair-skip-index",
            "repair-skip-index",
        )
        index_path = factory.path / ".vault" / "index" / "repair-skip-index.index.md"

        result = factory.run(
            "vault",
            "repair",
            "--feature",
            "repair-skip-index",
            "--no-index",
            "--json",
        )
        payload = _json_payload(result.output)
        index_phase = next(p for p in payload["phases"] if p["phase"] == "index")

        assert result.exit_code == 0
        assert index_phase["skipped"] is True
        assert payload["generated_indexes"] == []
        assert not index_path.exists()

    def test_check_order_and_info_visibility_are_stable(
        self,
        factory: WorkspaceFactory,
    ) -> None:
        factory.install("core")
        _write_doc(
            factory.path,
            "adr",
            "2026-05-15-info-visibility",
            "info-visibility",
        )

        json_result = factory.run("vault", "check", "all", "--json")
        payload = json.loads(json_result.output)
        assert [item["check_name"] for item in payload] == [
            "structure",
            "frontmatter",
            "links",
            "dangling",
            "body-links",
            "orphans",
            "features",
            "references",
            "schema",
        ]

        factory.run("vault", "feature", "index", "--feature", "info-visibility")
        default_result = factory.run(
            "vault",
            "check",
            "features",
            "--feature",
            "info-visibility",
        )
        verbose_result = factory.run(
            "vault",
            "check",
            "features",
            "--feature",
            "info-visibility",
            "--verbose",
        )

        assert "research document" not in default_result.output
        assert "research document" in verbose_result.output
