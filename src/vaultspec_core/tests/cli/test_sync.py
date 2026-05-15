"""Tests for sync command behavior."""

import json
import os

import pytest
from typer.testing import CliRunner

from vaultspec_core.cli import app

pytestmark = [pytest.mark.unit]


@pytest.fixture
def runner():
    return CliRunner()


class TestSyncCoreError:
    def test_sync_core_fails(self, runner, synthetic_project):
        """sync core must fail with clear error."""
        result = runner.invoke(
            app, ["--target", str(synthetic_project), "sync", "core"]
        )
        assert result.exit_code != 0
        assert "core" in result.output.lower()

    def test_sync_core_error_mentions_source(self, runner, synthetic_project):
        """Error should explain that core is the sync source."""
        result = runner.invoke(
            app, ["--target", str(synthetic_project), "sync", "core"]
        )
        assert (
            "source" in result.output.lower() or ".vaultspec" in result.output.lower()
        )


class TestSyncValidation:
    def test_sync_unknown_provider_fails(self, runner, synthetic_project):
        """Unknown provider name must fail."""
        result = runner.invoke(
            app, ["--target", str(synthetic_project), "sync", "nonexistent"]
        )
        assert result.exit_code != 0

    def test_sync_help_shows_providers(self, runner):
        """--help should list available providers."""
        result = runner.invoke(app, ["sync", "--help"])
        assert result.exit_code == 0
        assert "claude" in result.output
        assert "gemini" in result.output
        assert "codex" in result.output

    def test_sync_help_declares_mcp_as_complete_sync_scope(self, runner):
        """Top-level sync help should describe every authoritative sync pass."""
        result = runner.invoke(app, ["sync", "--help"])
        assert result.exit_code == 0
        assert "MCP" in result.output or "mcp" in result.output


class TestSyncAuthority:
    def test_rules_add_points_to_top_level_sync(self, runner, synthetic_project):
        """Adding a rule should not imply provider outputs were refreshed."""
        result = runner.invoke(
            app,
            [
                "--target",
                str(synthetic_project),
                "spec",
                "rules",
                "add",
                "--name",
                "operator-sync-guidance",
                "--content",
                "Keep provider stubs fresh.",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "Rule source updated" in result.output
        assert "Provider-facing outputs were not updated" in result.output
        assert "vaultspec-core sync" in result.output

    def test_rules_add_json_stays_machine_readable(self, runner, synthetic_project):
        """JSON mode should not include human remediation guidance."""
        result = runner.invoke(
            app,
            [
                "--target",
                str(synthetic_project),
                "spec",
                "rules",
                "add",
                "--name",
                "operator-sync-json",
                "--content",
                "Keep JSON parseable.",
                "--json",
            ],
        )
        payload = json.loads(result.output)

        assert result.exit_code == 0, result.output
        assert payload["path"].endswith("operator-sync-json.md")
        assert "Provider-facing outputs" not in result.output

    @pytest.mark.parametrize(
        ("args", "expected"),
        [
            (
                [
                    "spec",
                    "skills",
                    "add",
                    "--name",
                    "operator-skill-guidance",
                    "--description",
                    "Skill guidance",
                ],
                "Skill source updated",
            ),
            (
                [
                    "spec",
                    "agents",
                    "add",
                    "--name",
                    "operator-agent-guidance",
                    "--description",
                    "Agent guidance",
                ],
                "Agent source updated",
            ),
            (
                [
                    "spec",
                    "mcps",
                    "add",
                    "--name",
                    "operator-mcp-guidance",
                ],
                "MCP source updated",
            ),
        ],
    )
    def test_non_rule_source_mutations_point_to_top_level_sync(
        self, runner, synthetic_project, args, expected
    ):
        """All source-side spec mutations should give the same sync cue."""
        result = runner.invoke(app, ["--target", str(synthetic_project), *args])

        assert result.exit_code == 0, result.output
        assert expected in result.output
        assert "Provider-facing outputs were not updated" in result.output
        assert "vaultspec-core sync" in result.output

    def test_narrow_rules_sync_warns_about_resource_scope(
        self, runner, synthetic_project
    ):
        """Resource sync output should identify top-level sync as authoritative."""
        result = runner.invoke(
            app,
            ["--target", str(synthetic_project), "spec", "rules", "sync"],
        )
        assert result.exit_code == 0, result.output
        assert "Resource-scoped sync only" in result.output
        assert "vaultspec-core sync" in result.output
        assert "complete provider-facing refresh" in result.output

    def test_provider_scoped_sync_renders_only_requested_provider(
        self, runner, synthetic_project
    ):
        """`sync claude` output should not imply every provider was refreshed."""
        result = runner.invoke(
            app,
            ["--target", str(synthetic_project), "sync", "claude"],
        )

        assert result.exit_code == 0, result.output
        assert "Syncing 1 enabled providers" in result.output
        assert "claude" in result.output
        assert "gemini" not in result.output
        assert "antigravity" not in result.output
        assert "codex" not in result.output

    def test_rule_add_then_top_level_sync_updates_provider_stubs(
        self, runner, synthetic_project
    ):
        """Top-level sync must refresh provider stubs after a rule source change."""
        rule_name = "operator-sync-regression"
        old_cwd = os.getcwd()
        try:
            os.chdir(synthetic_project)
            add_result = runner.invoke(
                app,
                [
                    "spec",
                    "rules",
                    "add",
                    "--name",
                    rule_name,
                    "--content",
                    "Surface this rule in provider config stubs.",
                ],
            )
            assert add_result.exit_code == 0, add_result.output

            source_rule = (
                synthetic_project / ".vaultspec" / "rules" / "rules" / f"{rule_name}.md"
            )
            assert source_rule.exists(), f"Rule source missing: {source_rule}"

            sync_result = runner.invoke(app, ["sync"])
            assert sync_result.exit_code == 0, sync_result.output
        finally:
            os.chdir(old_cwd)

        expected = {
            "AGENTS.md": f"@.codex/rules/{rule_name}.md",
            "CLAUDE.md": f"@.claude/rules/{rule_name}.md",
            "GEMINI.md": f"{rule_name}.md",
        }
        for filename, marker in expected.items():
            path = synthetic_project / filename
            content = path.read_text(encoding="utf-8")
            assert marker in content, (
                f"{filename} missing {marker!r} after top-level sync.\n"
                f"Sync output:\n{sync_result.output}\n"
                f"Observed content:\n{content}"
            )
