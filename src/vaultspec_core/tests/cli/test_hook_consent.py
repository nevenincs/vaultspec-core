"""CLI-level consent behaviour for provider hooks.

A provider hook is the more dangerous of vaultspec's two consent surfaces. A
lifecycle trigger runs once, when vaultspec fires its event; a provider hook is
written into the agent's own configuration and runs there on every matching
tool call, long after the sync that rendered it, with nothing on screen. So a
developer who clones a repository and runs the documented ``sync`` must not have
the repository author's command installed into their agent, the refusal must say
why and how to resolve it, an unattended run must never answer for the operator,
and withdrawing approval must remove what was already written.

Everything is real: a real installed workspace, real hook files, a real sync,
and real provider config files inspected on disk afterwards. The consent ledger
lives under the machine-global VaultSpec home, so every invocation carries an
environment whose home is a directory the test owns - the developer's own ledger
is never read or written.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.cli import app
from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory

if TYPE_CHECKING:
    from pathlib import Path

    from typer.testing import CliRunner

pytestmark = [pytest.mark.unit]


def attended_env(home: Path) -> dict[str, str | None]:
    """Environment for a run with an operator's home and no CI marker."""
    return {
        "NO_COLOR": "1",
        "HOME": str(home),
        "USERPROFILE": str(home),
        "CI": None,
        "VAULTSPEC_NON_INTERACTIVE": None,
    }


def carried_workspace(tmp_path: Path) -> tuple[Path, Path]:
    """Install a workspace carrying the hook a cloned checkout would bring."""
    root = tmp_path / "project"
    root.mkdir()
    WorkspaceFactory(root).install("claude")

    home = tmp_path / "operator-home"
    home.mkdir()

    hooks_dir = root / ".vaultspec" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    (hooks_dir / "carried.yaml").write_text(
        "event: pre_tool_use\nmatcher: Bash\ncommand: echo CARRIED\n",
        encoding="utf-8",
    )
    return root, home


def claude_hooks(root: Path) -> dict:
    """Return the ``hooks`` mapping claude's settings file carries, if any."""
    settings = root / ".claude" / "settings.json"
    if not settings.exists():
        return {}
    loaded = json.loads(settings.read_text(encoding="utf-8"))
    return loaded.get("hooks", {})


def rendered_commands(root: Path) -> list[str]:
    """Every command string vaultspec wrote into claude's settings."""
    return [
        handler.get("command", "")
        for groups in claude_hooks(root).values()
        for group in groups
        for handler in group.get("hooks", [])
    ]


class TestUnapprovedHooksAreNotRendered:
    """A cloned repository's hook must not reach an agent's configuration."""

    def test_sync_all_without_a_grant_writes_nothing(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root, home = carried_workspace(tmp_path)
        monkeypatch.chdir(root)

        result = runner.invoke(
            app,
            ["sync"],
            input="",
            env=attended_env(home),
        )

        assert "CARRIED" not in " ".join(rendered_commands(root))
        assert "carried" in result.output.lower()

    def test_sync_one_provider_without_a_grant_writes_nothing(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The gate is not narrowed to the all-provider sync."""
        root, home = carried_workspace(tmp_path)
        monkeypatch.chdir(root)

        runner.invoke(
            app,
            ["sync", "claude"],
            input="",
            env=attended_env(home),
        )

        assert "CARRIED" not in " ".join(rendered_commands(root))

    def test_json_run_never_prompts_and_never_grants(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root, home = carried_workspace(tmp_path)
        monkeypatch.chdir(root)

        runner.invoke(
            app,
            ["sync", "--json"],
            input="y\n",
            env=attended_env(home),
        )

        assert "CARRIED" not in " ".join(rendered_commands(root))
        assert not (home / ".vaultspec" / "hook-trust.json").exists()

    def test_ci_marker_never_grants(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root, home = carried_workspace(tmp_path)
        monkeypatch.chdir(root)
        env = attended_env(home)
        env["CI"] = "1"

        runner.invoke(app, ["sync"], input="y\n", env=env)

        assert "CARRIED" not in " ".join(rendered_commands(root))
        assert not (home / ".vaultspec" / "hook-trust.json").exists()

    def test_the_refusal_names_the_file_and_the_verb(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root, home = carried_workspace(tmp_path)
        monkeypatch.chdir(root)

        result = runner.invoke(
            app,
            ["sync"],
            input="",
            env=attended_env(home),
        )

        assert "carried" in result.output.lower()
        assert "spec hooks trust" in result.output


class TestApprovalRendersAndRevocationWithdraws:
    """Approval is the whole workflow, and so is taking it back."""

    def test_trust_then_sync_renders_the_hook(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root, home = carried_workspace(tmp_path)
        monkeypatch.chdir(root)

        approved = runner.invoke(
            app,
            ["spec", "hooks", "trust"],
            env=attended_env(home),
        )
        assert approved.exit_code == 0, approved.output

        runner.invoke(app, ["sync"], env=attended_env(home))

        assert "echo CARRIED" in rendered_commands(root)

    def test_revoking_then_syncing_removes_what_was_rendered(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Revocation has to reach the provider file, not just the ledger.

        The sidecar records exactly what the last sync wrote, so withdrawing a
        grant and syncing again must take the hook back out of the agent's
        configuration. An approval that cannot be undone is not a consent
        mechanism.
        """
        root, home = carried_workspace(tmp_path)
        monkeypatch.chdir(root)
        runner.invoke(
            app,
            ["spec", "hooks", "trust"],
            env=attended_env(home),
        )
        runner.invoke(app, ["sync"], env=attended_env(home))
        assert "echo CARRIED" in rendered_commands(root)

        revoked = runner.invoke(
            app,
            ["spec", "hooks", "trust", "--revoke"],
            env=attended_env(home),
        )
        assert revoked.exit_code == 0, revoked.output

        runner.invoke(
            app,
            ["sync"],
            input="",
            env=attended_env(home),
        )

        assert "echo CARRIED" not in rendered_commands(root)

    def test_editing_an_approved_hook_withdraws_the_approval(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Consent is pinned to content, so a pulled change asks again."""
        root, home = carried_workspace(tmp_path)
        monkeypatch.chdir(root)
        runner.invoke(
            app,
            ["spec", "hooks", "trust"],
            env=attended_env(home),
        )
        runner.invoke(app, ["sync"], env=attended_env(home))
        assert "echo CARRIED" in rendered_commands(root)

        (root / ".vaultspec" / "hooks" / "carried.yaml").write_text(
            "event: pre_tool_use\nmatcher: Bash\ncommand: echo REPLACED\n",
            encoding="utf-8",
        )
        runner.invoke(
            app,
            ["sync"],
            input="",
            env=attended_env(home),
        )

        commands = rendered_commands(root)
        assert "echo REPLACED" not in commands
        assert "echo CARRIED" not in commands


class TestGrantsAreSeparatePerSystem:
    """Approving hooks must not approve triggers, or the reverse."""

    def test_trusting_hooks_does_not_trust_triggers(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root, home = carried_workspace(tmp_path)
        monkeypatch.chdir(root)
        triggers_dir = root / ".vaultspec" / "triggers"
        triggers_dir.mkdir(parents=True, exist_ok=True)
        (triggers_dir / "lifecycle.yaml").write_text(
            "event: config.synced\nenabled: true\n"
            "actions:\n  - type: shell\n    command: echo TRIGGER\n",
            encoding="utf-8",
        )

        runner.invoke(
            app,
            ["spec", "hooks", "trust"],
            env=attended_env(home),
        )
        listed = runner.invoke(
            app,
            ["spec", "triggers", "list", "--json"],
            env=attended_env(home),
        )

        payload = json.loads(listed.output)
        assert payload["data"]["triggers"][0]["trusted"] is False

    def test_hooks_trust_points_at_the_other_verb(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The one verb whose meaning changed says where the other grant is."""
        root, home = carried_workspace(tmp_path)
        monkeypatch.chdir(root)
        triggers_dir = root / ".vaultspec" / "triggers"
        triggers_dir.mkdir(parents=True, exist_ok=True)
        (triggers_dir / "lifecycle.yaml").write_text(
            "event: config.synced\nenabled: true\n"
            "actions:\n  - type: shell\n    command: echo TRIGGER\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["spec", "hooks", "trust"],
            env=attended_env(home),
        )

        assert "spec triggers trust" in result.output
