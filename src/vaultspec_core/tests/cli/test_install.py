"""Tests for install command behavior."""

import json

import pytest
from typer.testing import CliRunner

from vaultspec_core.cli import app

pytestmark = [pytest.mark.unit]


@pytest.fixture
def runner():
    return CliRunner()


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
