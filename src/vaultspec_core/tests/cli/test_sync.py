"""Tests for sync command behavior."""

import json
import os
import re

import pytest
from typer.testing import CliRunner

from vaultspec_core.cli import app
from vaultspec_core.core.manifest import read_manifest_data, write_manifest_data
from vaultspec_core.core.mcps import render_mcp_definition_for_mode
from vaultspec_core.core.workspace_mode import resolve_render_mode

pytestmark = [pytest.mark.unit]

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


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

    def test_sync_unknown_provider_json_emits_error_envelope(
        self, runner, synthetic_project
    ):
        """Under --json a failure must be a parseable error envelope,
        not a plain-text line a JSON consumer cannot read."""
        result = runner.invoke(
            app,
            ["--target", str(synthetic_project), "sync", "nonexistent", "--json"],
        )
        assert result.exit_code == 1
        payload = json.loads(result.output)
        assert payload["status"] == "failed"
        assert "nonexistent" in payload["data"]["message"]

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

    def test_sync_skip_core_is_rejected(self, runner, synthetic_project):
        """`core` is an install/uninstall component, not a sync skip target."""
        result = runner.invoke(
            app,
            ["--target", str(synthetic_project), "sync", "--skip", "core"],
        )

        assert result.exit_code != 0
        assert "core" in result.output
        assert "Invalid --skip" in result.output

    def test_mcp_status_json_reports_configured_entry(self, runner, synthetic_project):
        """MCP status should answer the narrow config-health question directly."""
        result = runner.invoke(
            app,
            ["--target", str(synthetic_project), "spec", "mcps", "status", "--json"],
        )

        payload = json.loads(result.output)["data"]
        assert result.exit_code == 0, result.output
        assert payload["status"] == "ok"
        assert payload["config_exists"] is True
        assert payload["definitions"] == ["vaultspec-core"]
        assert payload["configured"] == ["vaultspec-core"]

    def test_mcp_status_json_reports_missing_config(self, runner, synthetic_project):
        """A missing .mcp.json should be visible without running global doctor."""
        (synthetic_project / ".mcp.json").unlink()

        result = runner.invoke(
            app,
            ["--target", str(synthetic_project), "spec", "mcps", "status", "--json"],
        )

        payload = json.loads(result.output)["data"]
        assert result.exit_code == 1, result.output
        assert payload["status"] == "partial"
        assert payload["missing"] == ["vaultspec-core"]
        assert payload["providers"]["claude"]["status"] == "missing_config"

    def test_mcp_status_json_reports_managed_config_drift(
        self, runner, synthetic_project
    ):
        """Managed MCP entry drift should be visible before running repair sync."""
        mcp_path = synthetic_project / ".mcp.json"
        payload = json.loads(mcp_path.read_text(encoding="utf-8"))
        payload["mcpServers"]["vaultspec-core"]["args"] = ["run", "broken-server"]
        mcp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

        result = runner.invoke(
            app,
            ["--target", str(synthetic_project), "spec", "mcps", "status", "--json"],
        )

        status = json.loads(result.output)["data"]
        assert result.exit_code == 1, result.output
        assert status["status"] == "partial"
        assert status["drifted"] == ["vaultspec-core"]


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
                "operator-sync-guidance",
                "--body",
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
                "operator-sync-json",
                "--body",
                "Keep JSON parseable.",
                "--json",
            ],
        )
        payload = json.loads(result.output)["data"]

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
        assert "Scoped sync" in result.output
        assert "vaultspec-core sync" in result.output
        assert "full provider refresh" in result.output

    def test_provider_scoped_sync_renders_only_requested_provider(
        self, runner, synthetic_project
    ):
        """`sync claude` output should not imply every provider was refreshed."""
        result = runner.invoke(
            app,
            ["--target", str(synthetic_project), "sync", "claude"],
        )

        assert result.exit_code == 0, result.output
        output = ANSI_RE.sub("", result.output)
        # The grouped renderer sub-heads only the requested provider, so
        # the output never implies the others were refreshed.
        assert "claude" in output
        assert "gemini" not in output
        assert "antigravity" not in output
        assert "codex" not in output

    def test_provider_scoped_sync_repairs_only_requested_native_mcp_state(
        self, runner, synthetic_project
    ):
        """Provider-scoped sync repairs its native target without touching peers."""
        mcp_path = synthetic_project / ".mcp.json"
        codex_path = synthetic_project / ".codex" / "config.toml"
        codex_before = codex_path.read_bytes()
        payload = json.loads(mcp_path.read_text(encoding="utf-8"))
        payload["mcpServers"]["vaultspec-core"]["args"] = ["run", "broken-server"]
        mcp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

        result = runner.invoke(
            app,
            ["--target", str(synthetic_project), "sync", "claude", "--force"],
        )

        assert result.exit_code == 0, result.output
        repaired = json.loads(mcp_path.read_text(encoding="utf-8"))
        assert repaired["mcpServers"]["vaultspec-core"]["args"] != [
            "run",
            "broken-server",
        ]
        assert codex_path.read_bytes() == codex_before

    def test_provider_scoped_sync_respects_skip_for_requested_provider(
        self, runner, synthetic_project
    ):
        """`sync claude --skip claude` must not refresh Claude outputs."""
        claude_rule = next((synthetic_project / ".claude" / "rules").glob("*.md"))
        before = claude_rule.read_text(encoding="utf-8")
        mcp_path = synthetic_project / ".mcp.json"
        mcp_before = mcp_path.read_text(encoding="utf-8")
        claude_rule.write_text(before + "\nlocal drift\n", encoding="utf-8")

        result = runner.invoke(
            app,
            ["--target", str(synthetic_project), "sync", "claude", "--skip", "claude"],
        )

        assert result.exit_code == 0, result.output
        output = ANSI_RE.sub("", result.output)
        # Skipping the only requested provider leaves nothing to sync.
        assert "No enabled providers to sync" in output
        assert "Sync produced 0 files" not in output
        assert claude_rule.read_text(encoding="utf-8") == before + "\nlocal drift\n"
        assert mcp_path.read_text(encoding="utf-8") == mcp_before

    def test_sync_all_skip_does_not_stamp_skipped_provider(
        self, runner, synthetic_project
    ):
        """Skipped providers must not get fresh last_synced state."""
        mdata = read_manifest_data(synthetic_project)
        mdata.provider_state.setdefault("claude", {})["last_synced"] = "old-claude"
        mdata.provider_state.setdefault("gemini", {})["last_synced"] = "old-gemini"
        write_manifest_data(synthetic_project, mdata)

        result = runner.invoke(
            app,
            ["--target", str(synthetic_project), "sync", "--skip", "claude"],
        )

        assert result.exit_code == 0, result.output
        after = read_manifest_data(synthetic_project)
        assert after.provider_state["claude"]["last_synced"] == "old-claude"
        assert after.provider_state["gemini"]["last_synced"] != "old-gemini"

    def test_sync_all_deleted_gitignore_disables_management(
        self, runner, synthetic_project
    ):
        """Deleting managed .gitignore should opt out without crashing sync."""
        mdata = read_manifest_data(synthetic_project)
        mdata.gitignore_managed = True
        write_manifest_data(synthetic_project, mdata)
        gitignore_path = synthetic_project / ".gitignore"
        if gitignore_path.exists():
            gitignore_path.unlink()

        result = runner.invoke(app, ["--target", str(synthetic_project), "sync"])

        assert result.exit_code == 0, result.output
        assert read_manifest_data(synthetic_project).gitignore_managed is False

    def test_rule_add_then_top_level_sync_updates_provider_outputs(
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
                    rule_name,
                    "--body",
                    "Surface this rule in provider config stubs.",
                ],
            )
            assert add_result.exit_code == 0, add_result.output

            source_rule = synthetic_project / ".vaultspec" / "rules" / f"{rule_name}.md"
            assert source_rule.exists(), f"Rule source missing: {source_rule}"

            sync_result = runner.invoke(app, ["sync"])
            assert sync_result.exit_code == 0, sync_result.output
        finally:
            os.chdir(old_cwd)

        # Claude and Codex expand @ includes (reference form); agy does not, so
        # GEMINI.md embeds the rule body inline instead of referencing it.
        expected = {
            "AGENTS.md": f"@.codex/rules/{rule_name}.md",
            "CLAUDE.md": f"@.claude/rules/{rule_name}.md",
            "GEMINI.md": "Surface this rule in provider config stubs.",
        }
        for filename, marker in expected.items():
            path = synthetic_project / filename
            content = path.read_text(encoding="utf-8")
            assert marker in content, (
                f"{filename} missing {marker!r} after top-level sync.\n"
                f"Sync output:\n{sync_result.output}\n"
                f"Observed content:\n{content}"
            )

    def test_top_level_sync_force_repairs_only_managed_mcp_state(
        self, runner, synthetic_project
    ):
        """Forced sync repairs managed MCP drift without deleting user servers."""
        mcp_path = synthetic_project / ".mcp.json"
        source_path = (
            synthetic_project / ".vaultspec" / "mcps" / "vaultspec-core.builtin.json"
        )
        # The seeded builtin is mode-neutral (placeholder tokens); a workspace's
        # .mcp.json holds the launch command rendered for its resolved mode, so
        # the expected entry is the source rendered for that same mode.
        expected_config = render_mcp_definition_for_mode(
            json.loads(source_path.read_text(encoding="utf-8")),
            resolve_render_mode(synthetic_project),
        )

        payload = json.loads(mcp_path.read_text(encoding="utf-8"))
        payload["mcpServers"]["vaultspec-core"]["args"] = ["run", "broken-server"]
        payload["mcpServers"]["stale-managed"] = {
            "command": "node",
            "args": ["old-server.js"],
        }
        payload["mcpServers"]["user-server"] = {
            "command": "node",
            "args": ["user-server.js"],
        }
        payload["_vaultspecManaged"] = ["stale-managed", "vaultspec-core"]
        mcp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

        before = runner.invoke(
            app,
            ["--target", str(synthetic_project), "spec", "mcps", "status", "--json"],
        )
        before_status = json.loads(before.output)["data"]
        assert before.exit_code == 1, before.output
        assert before_status["drifted"] == ["vaultspec-core"]
        assert before_status["stale_managed"] == ["stale-managed"]

        sync_result = runner.invoke(
            app, ["--target", str(synthetic_project), "sync", "--force"]
        )

        assert sync_result.exit_code == 0, sync_result.output
        repaired = json.loads(mcp_path.read_text(encoding="utf-8"))
        assert repaired["mcpServers"]["vaultspec-core"] == expected_config
        assert "stale-managed" not in repaired["mcpServers"]
        assert repaired["mcpServers"]["user-server"] == {
            "command": "node",
            "args": ["user-server.js"],
        }
        assert "_vaultspecManaged" not in repaired
        ownership = json.loads(
            (synthetic_project / ".vaultspec" / "mcp-ownership.json").read_text(
                encoding="utf-8"
            )
        )
        assert set(ownership["targets"]["claude:project"]["managed"]) == {
            "vaultspec-core"
        }

        after = runner.invoke(
            app,
            ["--target", str(synthetic_project), "spec", "mcps", "status", "--json"],
        )
        after_status = json.loads(after.output)["data"]
        assert after.exit_code == 0, after.output
        assert after_status["status"] == "ok"

    def test_force_adopts_name_colliding_user_mcp_entry(
        self, runner, synthetic_project
    ):
        """--force adopts a name-colliding user .mcp.json entry (issue #120).

        When .mcp.json carries an entry whose name matches a source but is absent
        from the external ownership sidecar, a plain sync preserves it and points
        at --force. --force then overwrites and records it as managed.
        """
        mcp_path = synthetic_project / ".mcp.json"
        source_path = (
            synthetic_project / ".vaultspec" / "mcps" / "vaultspec-core.builtin.json"
        )
        # The seeded builtin is mode-neutral (placeholder tokens); a workspace's
        # .mcp.json holds the launch command rendered for its resolved mode, so
        # the expected entry is the source rendered for that same mode.
        expected_config = render_mcp_definition_for_mode(
            json.loads(source_path.read_text(encoding="utf-8")),
            resolve_render_mode(synthetic_project),
        )

        payload = {
            "mcpServers": {
                "vaultspec-core": {"command": "node", "args": ["user-authored.js"]}
            }
        }
        mcp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        ownership_path = synthetic_project / ".vaultspec" / "mcp-ownership.json"
        ownership_path.unlink()

        plain = runner.invoke(
            app,
            ["--target", str(synthetic_project), "spec", "mcps", "sync", "--json"],
        )
        assert "--force" in plain.output
        preserved = json.loads(mcp_path.read_text(encoding="utf-8"))
        assert preserved["mcpServers"]["vaultspec-core"]["args"] == ["user-authored.js"]
        plain_ownership = json.loads(ownership_path.read_text(encoding="utf-8"))
        assert "claude:project" not in plain_ownership["targets"]

        forced = runner.invoke(
            app,
            ["--target", str(synthetic_project), "spec", "mcps", "sync", "--force"],
        )
        assert forced.exit_code == 0, forced.output
        adopted = json.loads(mcp_path.read_text(encoding="utf-8"))
        assert adopted["mcpServers"]["vaultspec-core"] == expected_config
        assert "_vaultspecManaged" not in adopted
        ownership = json.loads(ownership_path.read_text(encoding="utf-8"))
        assert "vaultspec-core" in ownership["targets"]["claude:project"]["managed"]
