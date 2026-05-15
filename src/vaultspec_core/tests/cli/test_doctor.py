"""Tests for the ``vaultspec-core spec doctor`` CLI command."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]


class TestDoctorCommand:
    """Tests for the doctor CLI command output and exit codes."""

    def test_installed_workspace_does_not_error(self, tmp_path: Path) -> None:
        factory = WorkspaceFactory(tmp_path)
        factory.install()
        result = factory.run("spec", "doctor")
        assert result.exit_code in (0, 1)

    def test_output_contains_framework(self, tmp_path: Path) -> None:
        factory = WorkspaceFactory(tmp_path)
        factory.install()
        result = factory.run("spec", "doctor")
        assert "framework" in result.output.lower()

    def test_corrupted_manifest_exit_two(self, tmp_path: Path) -> None:
        factory = WorkspaceFactory(tmp_path)
        factory.install().corrupt_manifest()
        result = factory.run("spec", "doctor")
        assert result.exit_code == 2

    def test_json_output_valid(self, tmp_path: Path) -> None:
        factory = WorkspaceFactory(tmp_path)
        factory.install()
        result = factory.run("spec", "doctor", "--json")
        data = json.loads(result.output)
        assert "framework" in data
        assert "providers" in data
        assert "builtin_version" in data
        assert "gitignore" in data
        assert "gitattributes" in data
        assert "vault_content" in data

    def test_json_exit_code_reflects_corrupted_state(self, tmp_path: Path) -> None:
        factory = WorkspaceFactory(tmp_path)
        factory.install().corrupt_manifest()
        result = factory.run("spec", "doctor", "--json")
        assert result.exit_code == 2
        # The output may contain log warnings before the JSON payload.
        json_start = result.output.index("{")
        data = json.loads(result.output[json_start:])
        assert data["framework"] == "corrupted"

    def test_missing_framework_exit_two(self, tmp_path: Path) -> None:
        factory = WorkspaceFactory(tmp_path)
        result = factory.run("spec", "doctor")
        assert result.exit_code == 2

    def test_output_contains_provider_names(self, tmp_path: Path) -> None:
        factory = WorkspaceFactory(tmp_path)
        factory.install()
        result = factory.run("spec", "doctor")
        assert "claude" in result.output.lower()

    def test_output_contains_builtins_row(self, tmp_path: Path) -> None:
        factory = WorkspaceFactory(tmp_path)
        factory.install()
        result = factory.run("spec", "doctor")
        assert "builtins" in result.output.lower()

    def test_output_contains_gitignore_row(self, tmp_path: Path) -> None:
        factory = WorkspaceFactory(tmp_path)
        factory.install()
        result = factory.run("spec", "doctor")
        assert "gitignore" in result.output.lower()

    def test_output_contains_gitattributes_row(self, tmp_path: Path) -> None:
        factory = WorkspaceFactory(tmp_path)
        factory.install()
        result = factory.run("spec", "doctor")
        assert "gitattributes" in result.output.lower()

    def test_deleted_vaultspec_dir_exit_two(self, tmp_path: Path) -> None:
        factory = WorkspaceFactory(tmp_path)
        factory.install().delete_vaultspec_dir()
        result = factory.run("spec", "doctor")
        assert result.exit_code == 2

    def test_json_healthy_framework_present(self, tmp_path: Path) -> None:
        factory = WorkspaceFactory(tmp_path)
        factory.install()
        result = factory.run("spec", "doctor", "--json")
        data = json.loads(result.output)
        assert data["framework"] == "present"

    def test_single_provider_install_does_not_report_skipped_provider_drift(
        self, tmp_path: Path
    ) -> None:
        factory = WorkspaceFactory(tmp_path)
        factory.install("claude")

        result = factory.run("spec", "doctor")

        assert result.exit_code == 0
        assert "config: missing" not in result.output
        assert "file(s) need attention" not in result.output

    def test_core_only_install_does_not_report_provider_drift(
        self, tmp_path: Path
    ) -> None:
        factory = WorkspaceFactory(tmp_path)
        factory.install("core")

        result = factory.run("spec", "doctor")

        assert result.exit_code == 0
        assert "config: missing" not in result.output
        assert "file(s) need attention" not in result.output

    def test_skipped_mcp_is_not_rendered_as_unknown(self, tmp_path: Path) -> None:
        factory = WorkspaceFactory(tmp_path)
        factory.install(skip={"mcp"})

        result = factory.run("spec", "doctor")

        assert result.exit_code == 0
        assert "unknown (partial_mcp)" not in result.output
        assert ".mcp.json missing or incomplete" in result.output

    @pytest.mark.parametrize("provider", ["gemini", "codex"])
    def test_shared_agents_dir_does_not_report_antigravity_untracked(
        self, tmp_path: Path, provider: str
    ) -> None:
        factory = WorkspaceFactory(tmp_path)
        factory.install(provider)

        result = factory.run("spec", "doctor")

        assert result.exit_code == 0
        assert "manifest: untracked" not in result.output
        assert "antigravity" in result.output.lower()
        assert "file(s) need attention" not in result.output

    def test_doctor_reports_vault_annotations_without_mutating(
        self, tmp_path: Path
    ) -> None:
        factory = WorkspaceFactory(tmp_path)
        factory.install("core")
        doc = tmp_path / ".vault" / "research" / "2026-05-15-doctor.md"
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text(
            "---\n"
            "tags:\n"
            "  - '#research'\n"
            "  - '#doctor-annotations'\n"
            "date: '2026-05-15'\n"
            "related: []\n"
            "---\n"
            "\n"
            "<!-- Fill this generated scaffold before committing. -->\n"
            "\n"
            "# Doctor annotations\n",
            encoding="utf-8",
        )

        result = factory.run("spec", "doctor")

        assert result.exit_code == 1
        output = result.output.lower()
        assert "vault content" in output
        assert "generated template" in output
        assert "annotations" in output
        assert "vaultspec-core" in output
        assert "vault sanitize" in output
        assert "<!-- Fill" in doc.read_text(encoding="utf-8")

    def test_doctor_json_reports_vault_annotation_signal(self, tmp_path: Path) -> None:
        factory = WorkspaceFactory(tmp_path)
        factory.install("core")
        doc = tmp_path / ".vault" / "research" / "2026-05-15-doctor-json.md"
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text(
            "---\n"
            "tags:\n"
            "  - '#research'\n"
            "  - '#doctor-json-annotations'\n"
            "date: '2026-05-15'\n"
            "related: []\n"
            "---\n"
            "\n"
            "<!-- Generated instruction. -->\n"
            "\n"
            "# Doctor JSON annotations\n",
            encoding="utf-8",
        )

        result = factory.run("spec", "doctor", "--json")

        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["vault_content"] == "annotations"
        assert data["vault_annotation_count"] == 1
        assert "<!-- Generated instruction." in doc.read_text(encoding="utf-8")

    def test_doctor_json_reports_unreadable_vault_markdown(
        self, tmp_path: Path
    ) -> None:
        factory = WorkspaceFactory(tmp_path)
        factory.install("core")
        bad_doc = tmp_path / ".vault" / "research" / "2026-05-15-unreadable.md"
        bad_doc.parent.mkdir(parents=True, exist_ok=True)
        bad_doc.write_bytes(b"\xff\xfe\xfa")

        result = factory.run("spec", "doctor", "--json")

        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["vault_content"] == "unreadable"
        assert data["vault_unreadable_count"] == 1
