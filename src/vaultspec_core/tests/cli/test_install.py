"""Tests for install command behavior."""

import json

import pytest
from typer.testing import CliRunner

from vaultspec_core.cli import app

pytestmark = [pytest.mark.unit]


@pytest.fixture
def runner():
    return CliRunner()


class TestProviderRegistry:
    """The provider vocabulary derives from one source (the Tool enum)."""

    def test_provider_sets_derive_from_tool_enum(self):
        from vaultspec_core.core.commands import (
            _PROVIDER_TO_TOOLS,
            SYNC_PROVIDERS,
            VALID_PROVIDERS,
        )
        from vaultspec_core.core.enums import Tool

        # Every tool has a single-tool entry; the aggregate selectors are present.
        for tool in Tool:
            assert _PROVIDER_TO_TOOLS[tool.value] == [tool]
        assert _PROVIDER_TO_TOOLS["all"] == list(Tool)
        assert _PROVIDER_TO_TOOLS["core"] == []

        # Derived sets stay consistent with the map - no second hand-listed copy.
        assert set(_PROVIDER_TO_TOOLS) == VALID_PROVIDERS
        assert VALID_PROVIDERS - {"core"} == SYNC_PROVIDERS


class TestInstallForce:
    def test_install_without_force_fails_if_exists(self, tmp_path, runner):
        """Without --force, install must fail if .vaultspec/ exists."""
        (tmp_path / ".vaultspec").mkdir()
        result = runner.invoke(app, ["-t", str(tmp_path), "install"])
        assert result.exit_code != 0

    def test_install_force_proceeds_if_exists(self, tmp_path, runner):
        """--force allows reinstall over existing .vaultspec/."""
        (tmp_path / ".vaultspec").mkdir()
        result = runner.invoke(app, ["-t", str(tmp_path), "install", "--force"])
        # Should not error about already installed
        if result.exit_code != 0:
            assert "already installed" not in result.output.lower()

    def test_install_api_refuses_success_when_native_mcp_reconciliation_fails(
        self, tmp_path
    ):
        """A native-store parse failure is a typed install failure, not success."""
        from vaultspec_core.core.commands import install_run
        from vaultspec_core.core.exceptions import VaultSpecError

        (tmp_path / ".mcp.json").write_text("not valid json", encoding="utf-8")

        with pytest.raises(
            VaultSpecError,
            match="MCP provider-native enrollment failed",
        ):
            install_run(tmp_path, provider="claude", force=True)

    def test_install_cli_exits_nonzero_when_native_mcp_reconciliation_fails(
        self, tmp_path, runner
    ):
        """The CLI exposes the native-store failure and exits non-zero."""
        (tmp_path / ".mcp.json").write_text("not valid json", encoding="utf-8")

        result = runner.invoke(
            app,
            ["-t", str(tmp_path), "install", "claude", "--force"],
        )

        assert result.exit_code == 1, result.output
        assert "MCP provider-native enrollment failed" in result.output
        assert "Cannot parse" in result.output


class TestInstallJson:
    def test_install_json_stdout_is_parseable(self, tmp_path, runner):
        """JSON mode must not prepend preflight warnings to stdout."""
        result = runner.invoke(app, ["-t", str(tmp_path), "install", "--json"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)["data"]
        assert payload["action"] == "install"
        assert payload["has_mcp"] is True


class TestInstallDryRun:
    def test_dry_run_does_not_use_would_wording(self, tmp_path, runner):
        """--dry-run must NOT use 'Would create:' wording."""
        result = runner.invoke(app, ["-t", str(tmp_path), "install", "--dry-run"])
        assert result.exit_code == 0
        assert "would create" not in result.output.lower()

    def test_dry_run_produces_output(self, tmp_path, runner):
        """--dry-run must produce tree output."""
        result = runner.invoke(app, ["-t", str(tmp_path), "install", "--dry-run"])
        assert result.exit_code == 0
        assert len(result.output.strip()) > 0

    def test_dry_run_lists_individual_provider_files(self, synthetic_project, runner):
        """On an installed workspace, the preview lists provider files, not just dirs.

        Regression for the sparse install --dry-run output: provider work was
        previewed at directory granularity (a single ``claude (rules)`` line)
        while sync previewed per file. The preview now enumerates the files
        sync would deploy, matching sync's granularity.
        """
        result = runner.invoke(
            app, ["-t", str(synthetic_project), "install", "--force", "--dry-run"]
        )
        assert result.exit_code == 0, result.output
        # An individual builtin rule file appears, not only the directory line.
        assert "vaultspec-cli.builtin.md" in result.output


def _write_pyproject_with_vaultspec(root, *, section: str) -> None:
    """Write a pyproject.toml declaring vaultspec-core in *section*.

    *section* is one of ``"runtime"`` (``[project.dependencies]``) or ``"dev"``
    (the default ``[dependency-groups].dev`` group).
    """
    body = '[project]\nname = "example"\nversion = "0.0.0"\n'
    if section == "runtime":
        body += 'dependencies = ["vaultspec-core"]\n'
    elif section == "dev":
        body += '\n[dependency-groups]\ndev = ["vaultspec-core"]\n'
    (root / "pyproject.toml").write_text(body, encoding="utf-8")


def _advisory_present(output: str) -> bool:
    """Return whether the canonical dependency-leak advisory is in *output*.

    Both strings are whitespace-normalized so the console's line wrapping does
    not break the match. The single canonical constant is the only marker, so
    the advisory wording lives in exactly one place.
    """
    from vaultspec_core.core.workspace_mode import DEPENDENCY_LEAK_ADVISORY

    normalized = " ".join(output.split())
    return " ".join(DEPENDENCY_LEAK_ADVISORY.split()) in normalized


class TestDependencyLeakAdvisory:
    """Moment-of-choice dependency-leak advisory (install-parity ADR D3).

    The advisory fires only when a run newly elects dependency mode - an
    explicit ``--mode dependency`` flag or detection resolving to it - and stays
    silent when the mode is merely read from an existing persisted declaration.
    """

    def test_explicit_dependency_install_warns(self, tmp_path, runner):
        _write_pyproject_with_vaultspec(tmp_path, section="runtime")
        result = runner.invoke(
            app, ["-t", str(tmp_path), "install", "--mode", "dependency"]
        )
        assert result.exit_code == 0, result.output
        assert _advisory_present(result.output)

    def test_detected_dependency_install_warns(self, tmp_path, runner):
        # No --mode flag: detection resolves dependency mode from the runtime
        # dependency listing, which is still a fresh election.
        _write_pyproject_with_vaultspec(tmp_path, section="runtime")
        result = runner.invoke(app, ["-t", str(tmp_path), "install"])
        assert result.exit_code == 0, result.output
        assert _advisory_present(result.output)

    def test_persisted_dependency_reinstall_is_silent(self, tmp_path, runner):
        # First install elects dependency mode and persists it.
        _write_pyproject_with_vaultspec(tmp_path, section="runtime")
        first = runner.invoke(
            app, ["-t", str(tmp_path), "install", "--mode", "dependency"]
        )
        assert first.exit_code == 0, first.output
        assert _advisory_present(first.output)

        # Second install reads the persisted declaration: no fresh choice, so no
        # advisory. This is the core of the review fix.
        second = runner.invoke(app, ["-t", str(tmp_path), "install", "--force"])
        assert second.exit_code == 0, second.output
        assert not _advisory_present(second.output)

    def test_tool_mode_install_is_silent(self, tmp_path, runner):
        result = runner.invoke(app, ["-t", str(tmp_path), "install", "--mode", "tool"])
        assert result.exit_code == 0, result.output
        assert not _advisory_present(result.output)

    def test_dependency_dry_run_persisted_is_silent(self, tmp_path, runner):
        # install --dry-run on a workspace already declaring dependency mode must
        # not print the advisory (the review's explicit verify criterion).
        _write_pyproject_with_vaultspec(tmp_path, section="runtime")
        first = runner.invoke(
            app, ["-t", str(tmp_path), "install", "--mode", "dependency"]
        )
        assert first.exit_code == 0, first.output

        preview = runner.invoke(app, ["-t", str(tmp_path), "install", "--dry-run"])
        assert preview.exit_code == 0, preview.output
        assert not _advisory_present(preview.output)


class TestInstallPathSafety:
    def test_deep_nonexistent_path_rejected(self, tmp_path, runner):
        """Installing to a deeply nested non-existent path must fail."""
        target = tmp_path / "a" / "b" / "c" / "project"
        result = runner.invoke(app, ["-t", str(target), "install"])
        assert result.exit_code != 0
        assert "parent directory does not exist" in result.output.lower()
        # Must NOT have created any directories
        assert not (tmp_path / "a").exists()

    def test_single_level_nonexistent_path_creates_dir(self, tmp_path, runner):
        """Installing to a single-level non-existent path should create it."""
        target = tmp_path / "my-project"
        result = runner.invoke(app, ["-t", str(target), "install"])
        assert result.exit_code == 0
        assert target.exists()
        assert (target / ".vaultspec").exists()

    def test_dry_run_nonexistent_path_no_side_effects(self, tmp_path, runner):
        """Dry-run on a non-existent path must not create the directory."""
        target = tmp_path / "phantom"
        runner.invoke(app, ["-t", str(target), "install", "--dry-run"])
        # The key invariant: dry-run must never create the target directory
        assert not target.exists()


class TestSharingPolicy:
    """install and upgrade state the team-shared gitignore policy."""

    def test_install_prints_sharing_policy(self, tmp_path, runner):
        """A fresh install states the spec-layer sharing policy plainly."""
        result = runner.invoke(app, ["-t", str(tmp_path), "install"])
        assert result.exit_code == 0, result.output
        assert "Sharing policy" in result.output

    def test_dry_run_install_omits_sharing_policy(self, tmp_path, runner):
        """A dry-run previews changes; it does not state the policy."""
        result = runner.invoke(app, ["-t", str(tmp_path), "install", "--dry-run"])
        assert result.exit_code == 0
        assert "Sharing policy" not in result.output

    def test_upgrade_off_pre_reversal_block_prints_sharing_policy(
        self, tmp_path, runner
    ):
        """Upgrading a workspace still on the pre-reversal policy states it."""
        from vaultspec_core.core.gitignore import MARKER_BEGIN, MARKER_END

        runner.invoke(app, ["-t", str(tmp_path), "install"])
        # Plant a pre-reversal managed block (blanket-ignores the spec layer).
        old_block = "\n".join(
            [MARKER_BEGIN, ".vaultspec/", ".mcp.json", ".vault/logs/", MARKER_END]
        )
        (tmp_path / ".gitignore").write_text(
            f"# project\n\n{old_block}\n", encoding="utf-8"
        )

        result = runner.invoke(app, ["-t", str(tmp_path), "install", "--upgrade"])
        assert result.exit_code == 0, result.output
        assert "Sharing policy" in result.output

    def test_upgrade_of_current_workspace_omits_sharing_policy(self, tmp_path, runner):
        """Re-upgrading an already-team-shared workspace stays quiet."""
        runner.invoke(app, ["-t", str(tmp_path), "install"])

        result = runner.invoke(app, ["-t", str(tmp_path), "install", "--upgrade"])
        assert result.exit_code == 0, result.output
        assert "Sharing policy" not in result.output
