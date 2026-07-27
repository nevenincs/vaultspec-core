"""Tests for the ``vaultspec-core spec doctor`` CLI command."""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from vaultspec_core.cli import app
from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory

if TYPE_CHECKING:
    from pathlib import Path

    from typer.testing import Result

pytestmark = [pytest.mark.unit]


class TestDoctorCommand:
    """Tests for the doctor CLI command output and exit codes."""

    def test_installed_workspace_does_not_error(self, tmp_path: Path) -> None:
        factory = WorkspaceFactory(tmp_path)
        factory.install()
        result = factory.run("spec", "doctor")
        assert result.exit_code == 0, (
            f"freshly-installed workspace did not report healthy: "
            f"exit={result.exit_code}\n{result.output}"
        )

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
        data = json.loads(result.output)["data"]
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
        data = json.loads(result.output)["data"]
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
        data = json.loads(result.output)["data"]
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
        data = json.loads(result.output)["data"]
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
        data = json.loads(result.output)["data"]
        assert data["vault_content"] == "unreadable"
        assert data["vault_unreadable_count"] == 1


class TestTopLevelDoctorCommand:
    """Tests for the composed top-level doctor CLI command."""

    def test_top_level_doctor_healthy(self, tmp_path: Path) -> None:
        factory = WorkspaceFactory(tmp_path)
        factory.install()
        result = factory.run("doctor")
        assert result.exit_code in (0, 1)
        assert "vault check" in result.output.lower()

    def test_top_level_doctor_json_healthy(self, tmp_path: Path) -> None:
        factory = WorkspaceFactory(tmp_path)
        factory.install()
        result = factory.run("doctor", "--json")
        assert result.exit_code in (0, 1)
        data = json.loads(result.output)
        assert "schema" in data
        assert data["schema"] == "vaultspec.doctor.v1"
        assert "status" in data
        assert "data" in data
        assert "spec" in data["data"]
        assert "vault" in data["data"]
        assert "checks" in data["data"]["vault"]

    def test_top_level_doctor_missing_framework_exit_two(self, tmp_path: Path) -> None:
        factory = WorkspaceFactory(tmp_path)
        result = factory.run("doctor")
        assert result.exit_code == 2


class TestDoctorGateErrors:
    """``spec doctor --gate-errors`` folds the warning exit to 0.

    The ``spec-check`` pre-commit hook opts into this so warning-level
    provider-mirror lag - the expected steady state after any builtins
    change - never deadlocks commits, while real errors still fail the gate.
    Each test drives the real CLI against an on-disk workspace built by the
    factory; no doubles.
    """

    def test_warning_state_fails_without_flag(self, tmp_path: Path) -> None:
        # Stale synced provider content is a warning (exit 1) - the bare hook
        # form that deadlocks commits.
        factory = WorkspaceFactory(tmp_path)
        factory.install().outdated_vaultspec_rules("claude")
        # Assert the setup actually produced the drift the exit code depends on,
        # so a fixture that fails to stale anything fails loudly here instead of
        # as a bare exit-code mismatch.
        diagnosis = json.loads(factory.run("spec", "doctor", "--json").output)
        content = diagnosis["data"]["providers"]["claude"]["content"]
        assert "diverged" in content.values(), content
        result = factory.run("spec", "doctor")
        assert result.exit_code == 1, result.output

    def test_gate_errors_folds_warning_to_zero(self, tmp_path: Path) -> None:
        factory = WorkspaceFactory(tmp_path)
        factory.install().outdated_vaultspec_rules("claude")
        result = factory.run("spec", "doctor", "--gate-errors")
        assert result.exit_code == 0, result.output

    def test_gate_errors_still_fails_on_error(self, tmp_path: Path) -> None:
        # A corrupted manifest is an error (exit 2); the gate must still fail.
        factory = WorkspaceFactory(tmp_path)
        factory.install().corrupt_manifest()
        result = factory.run("spec", "doctor", "--gate-errors")
        assert result.exit_code == 2, result.output

    def test_gate_errors_clean_is_zero(self, tmp_path: Path) -> None:
        factory = WorkspaceFactory(tmp_path)
        factory.install()
        result = factory.run("spec", "doctor", "--gate-errors")
        assert result.exit_code == 0, result.output

    def test_gate_errors_json_folds_warning(self, tmp_path: Path) -> None:
        factory = WorkspaceFactory(tmp_path)
        factory.install().outdated_vaultspec_rules("claude")
        result = factory.run("spec", "doctor", "--gate-errors", "--json")
        assert result.exit_code == 0, result.output
        # The report still records the warning; only the exit code is folded.
        assert json.loads(result.output)["data"]["providers"]


# ---- Target precedence -------------------------------------------------------

#: Filename of the deliberately malformed document the vault-half tests plant.
#: Its directory tag contradicts its directory, so every checker pass over the
#: workspace holding it names it - and no pass over the other workspace can.
PROBE_DOC = "2026-05-15-target-probe-research.md"


def _workspace(root: Path, *, corrupt: bool = False) -> Path:
    """Install a real workspace at *root*, optionally corrupting its manifest."""
    root.mkdir(parents=True, exist_ok=True)
    factory = WorkspaceFactory(root)
    factory.install("core")
    if corrupt:
        factory.corrupt_manifest()
    return root


def _plant_probe_doc(root: Path) -> None:
    """Write one vault document whose directory tag contradicts its directory."""
    doc = root / ".vault" / "research" / PROBE_DOC
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text(
        "---\n"
        "tags:\n"
        "  - '#plan'\n"
        "  - '#target-probe'\n"
        "date: '2026-05-15'\n"
        "modified: '2026-05-15'\n"
        "related: []\n"
        "---\n"
        "\n"
        "# `target-probe` research: probe\n",
        encoding="utf-8",
    )


def _run_from(cwd: Path, *args: str) -> Result:
    """Invoke the real CLI with *cwd* as the process working directory."""
    from vaultspec_core.console import reset_console

    reset_console()
    runner = CliRunner(env={"NO_COLOR": "1"})
    previous_cwd = os.getcwd()
    os.chdir(cwd)
    try:
        return runner.invoke(app, list(args))
    finally:
        os.chdir(previous_cwd)


class TestDoctorTargetPrecedence:
    """``--target`` at either flag position selects the diagnosed directory.

    The documented priority is subcommand ``--target`` > root-level ``-t`` >
    current working directory. A CI invocation that puts the flag before the
    verb must therefore diagnose the named directory, never the process
    working directory: diagnosing the wrong tree reports someone else's
    health and exits on someone else's findings, which reads as a pass.

    Each test installs two real workspaces, runs the real CLI from inside
    one of them, and asserts on the other's diagnosis.
    """

    def test_spec_doctor_honours_root_level_target_over_cwd(
        self, tmp_path: Path
    ) -> None:
        healthy = _workspace(tmp_path / "healthy")
        broken = _workspace(tmp_path / "broken", corrupt=True)

        result = _run_from(healthy, "-t", str(broken), "spec", "doctor", "--json")

        assert result.exit_code == 2, result.output
        assert json.loads(result.output)["data"]["framework"] == "corrupted"

    def test_spec_doctor_subcommand_target_overrides_root_level(
        self, tmp_path: Path
    ) -> None:
        healthy = _workspace(tmp_path / "healthy")
        broken = _workspace(tmp_path / "broken", corrupt=True)

        result = _run_from(
            broken,
            "-t",
            str(broken),
            "spec",
            "doctor",
            "--target",
            str(healthy),
            "--json",
        )

        assert result.exit_code == 0, result.output
        assert json.loads(result.output)["data"]["framework"] == "present"

    def test_spec_doctor_falls_back_to_cwd_without_any_target(
        self, tmp_path: Path
    ) -> None:
        _workspace(tmp_path / "healthy")
        broken = _workspace(tmp_path / "broken", corrupt=True)

        result = _run_from(broken, "spec", "doctor", "--json")

        assert result.exit_code == 2, result.output
        assert json.loads(result.output)["data"]["framework"] == "corrupted"

    def test_doctor_honours_root_level_target_over_cwd(self, tmp_path: Path) -> None:
        healthy = _workspace(tmp_path / "healthy")
        broken = _workspace(tmp_path / "broken", corrupt=True)

        result = _run_from(healthy, "-t", str(broken), "doctor", "--json")

        assert result.exit_code == 2, result.output
        data = json.loads(result.output)["data"]
        assert data["spec"]["framework"] == "corrupted"

    def test_doctor_subcommand_target_overrides_root_level(
        self, tmp_path: Path
    ) -> None:
        healthy = _workspace(tmp_path / "healthy")
        broken = _workspace(tmp_path / "broken", corrupt=True)

        result = _run_from(
            broken, "-t", str(broken), "doctor", "--target", str(healthy), "--json"
        )

        data = json.loads(result.output)["data"]
        assert data["spec"]["framework"] == "present", result.output

    def test_doctor_falls_back_to_cwd_without_any_target(self, tmp_path: Path) -> None:
        _workspace(tmp_path / "healthy")
        broken = _workspace(tmp_path / "broken", corrupt=True)

        result = _run_from(broken, "doctor", "--json")

        assert result.exit_code == 2, result.output
        data = json.loads(result.output)["data"]
        assert data["spec"]["framework"] == "corrupted"

    def test_doctor_vault_checks_run_against_root_level_target(
        self, tmp_path: Path
    ) -> None:
        clean = _workspace(tmp_path / "clean")
        flawed = _workspace(tmp_path / "flawed")
        _plant_probe_doc(flawed)

        result = _run_from(clean, "-t", str(flawed), "doctor", "--json")

        # The vault half runs over the target, so its findings name the
        # document that exists only there.
        assert PROBE_DOC in result.output, result.output

    def test_doctor_vault_checks_ignore_cwd_when_target_given(
        self, tmp_path: Path
    ) -> None:
        clean = _workspace(tmp_path / "clean")
        flawed = _workspace(tmp_path / "flawed")
        _plant_probe_doc(flawed)

        result = _run_from(flawed, "-t", str(clean), "doctor", "--json")

        # The working directory holds the flawed document; the target does
        # not, so no finding may name it.
        assert PROBE_DOC not in result.output, result.output
