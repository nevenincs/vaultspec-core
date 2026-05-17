"""Tests for the unified __main__.py CLI router."""

from __future__ import annotations

import pytest

from vaultspec_core.cli import app

pytestmark = [pytest.mark.unit]


class TestMainHelp:
    """Verify that help output is printed for --help, -h, and no-args."""

    def test_help_flag(self, runner, synthetic_project):
        """--help exits 0."""
        result = runner.invoke(app, ["--target", str(synthetic_project), "--help"])
        assert result.exit_code == 0
        assert "vaultspec-core" in result.output

    def test_help_no_args(self, runner, synthetic_project):
        """No arguments exits 0 and prints help text."""
        result = runner.invoke(app, ["--target", str(synthetic_project)])
        assert result.exit_code == 0
        assert "vaultspec-core" in result.output

    def test_help_h_flag(self, runner, synthetic_project):
        """-h is rejected because the CLI only exposes --help."""
        result = runner.invoke(app, ["--target", str(synthetic_project), "-h"])
        assert result.exit_code != 0
        assert "No such option: -h" in result.output


class TestMainVersion:
    """Verify --version and -V print the version string."""

    def test_version_long(self, runner, synthetic_project):
        """--version exits 0 and output contains the version string."""
        from vaultspec_core.cli_common import get_version

        expected_version = get_version()
        result = runner.invoke(app, ["--target", str(synthetic_project), "--version"])
        assert result.exit_code == 0
        assert expected_version in result.output

    def test_version_short(self, runner, synthetic_project):
        """-V exits 0 and prints the same version."""
        from vaultspec_core.cli_common import get_version

        expected_version = get_version()
        result = runner.invoke(app, ["--target", str(synthetic_project), "-V"])
        assert result.exit_code == 0
        assert expected_version in result.output


class TestNamespaceRouting:
    """Verify that namespace commands route to the correct sub-CLI."""

    def test_vault_namespace_help(self, runner, synthetic_project):
        """``vaultspec-core vault --help`` exits 0 and shows subcommands."""
        result = runner.invoke(
            app, ["--target", str(synthetic_project), "vault", "--help"]
        )
        assert result.exit_code == 0
        assert "add" in result.output
        assert "check" in result.output

    def test_spec_namespace_help(self, runner, synthetic_project):
        """``vaultspec-core spec --help`` exits 0 and shows subcommands."""
        result = runner.invoke(
            app, ["--target", str(synthetic_project), "spec", "--help"]
        )
        assert result.exit_code == 0
        assert "rules" in result.output
        assert "skills" in result.output


class TestSpecCliFallthrough:
    """Verify commands under the spec group are routed correctly."""

    def test_rules_help(self, runner, synthetic_project):
        """``vaultspec-core spec rules --help`` exits 0 and shows rules subcommands."""
        result = runner.invoke(
            app, ["--target", str(synthetic_project), "spec", "rules", "--help"]
        )
        assert result.exit_code == 0
        assert "list" in result.output

    def test_skills_help(self, runner, synthetic_project):
        """``vaultspec-core spec skills --help`` exits 0."""
        result = runner.invoke(
            app, ["--target", str(synthetic_project), "spec", "skills", "--help"]
        )
        assert result.exit_code == 0

    def test_vault_check_all_runs(self, runner, synthetic_project):
        """``vaultspec-core vault check all`` exits 0 and shows check results."""
        result = runner.invoke(
            app, ["--target", str(synthetic_project), "vault", "check", "all"]
        )
        # The synthetic_project fixture deterministically seeds documents
        # that surface filename-rename warnings (n_docs=24, seed=42). The
        # contract for that corpus is exit_code 1 with a non-empty
        # rendered Vault Check report; exit 0 would mean the check
        # pipeline missed the seeded warnings and exit 2 would mean it
        # crashed.
        assert result.exit_code == 1, (
            f"vault check all on synthetic_project produced unexpected exit: "
            f"exit={result.exit_code}\n{result.output}"
        )
        assert "Vault Check" in result.output
        assert "fix:" in result.output, (
            f"synthetic corpus warnings did not surface fix hints: "
            f"{result.output}"
        )

    def test_unknown_command_fails(self, runner, synthetic_project):
        """``vaultspec nonexistent`` fails."""
        result = runner.invoke(app, ["--target", str(synthetic_project), "nonexistent"])
        assert result.exit_code != 0

    def test_root_mcp_subcommand_is_unknown(self, runner, synthetic_project):
        """``vaultspec-core mcp`` is rejected because MCP ships separately."""
        result = runner.invoke(app, ["--target", str(synthetic_project), "mcp"])
        assert result.exit_code != 0
        assert "No such command" in result.output
