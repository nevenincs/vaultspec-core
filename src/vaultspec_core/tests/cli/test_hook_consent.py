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
import os
import subprocess
import sys
from typing import TYPE_CHECKING, Any, cast

import pytest

from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]


def run_cli(
    *args: str, cwd: Path, home: Path, stdin: str = "", ci: bool = False
) -> subprocess.CompletedProcess[str]:
    """Run the real CLI in *cwd*, with the ledger under a home the test owns.

    A subprocess rather than an in-process runner, because a provider hook is
    read from the workspace the command runs in: the working directory is part
    of what is under test, and cannot be simulated without patching something.
    """
    env = dict(os.environ)
    env.update({"NO_COLOR": "1", "HOME": str(home), "USERPROFILE": str(home)})
    env.pop("VAULTSPEC_NON_INTERACTIVE", None)
    if ci:
        env["CI"] = "1"
    else:
        env.pop("CI", None)
    return subprocess.run(
        [sys.executable, "-m", "vaultspec_core", *args],
        cwd=cwd,
        env=env,
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )


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


def claude_hooks(root: Path) -> dict[str, Any]:
    """Return the ``hooks`` mapping claude's settings file carries, if any."""
    settings = root / ".claude" / "settings.json"
    if not settings.exists():
        return {}
    loaded = cast("dict[str, Any]", json.loads(settings.read_text(encoding="utf-8")))
    hooks = loaded.get("hooks", {})
    return cast("dict[str, Any]", hooks) if isinstance(hooks, dict) else {}


def rendered_commands(root: Path) -> list[str]:
    """Every command string vaultspec wrote into claude's settings."""
    commands: list[str] = []
    for groups in claude_hooks(root).values():
        for group in cast("list[dict[str, Any]]", groups):
            for handler in cast("list[dict[str, Any]]", group.get("hooks", [])):
                command = handler.get("command", "")
                if isinstance(command, str):
                    commands.append(command)
    return commands


class TestUnapprovedHooksAreNotRendered:
    """A cloned repository's hook must not reach an agent's configuration."""

    def test_sync_all_without_a_grant_writes_nothing(self, tmp_path: Path) -> None:
        root, home = carried_workspace(tmp_path)

        result = run_cli("sync", cwd=root, home=home)

        assert "CARRIED" not in " ".join(rendered_commands(root))
        assert "carried" in (result.stdout + result.stderr).lower()

    def test_sync_one_provider_without_a_grant_writes_nothing(
        self, tmp_path: Path
    ) -> None:
        """The gate is not narrowed to the all-provider sync."""
        root, home = carried_workspace(tmp_path)

        run_cli("sync", "claude", cwd=root, home=home)

        assert "CARRIED" not in " ".join(rendered_commands(root))

    def test_json_run_never_prompts_and_never_grants(self, tmp_path: Path) -> None:
        root, home = carried_workspace(tmp_path)

        run_cli("sync", "--json", cwd=root, home=home, stdin="y\n")

        assert "CARRIED" not in " ".join(rendered_commands(root))
        assert not (home / ".vaultspec" / "hook-trust.json").exists()

    def test_ci_marker_never_grants(self, tmp_path: Path) -> None:
        root, home = carried_workspace(tmp_path)

        run_cli("sync", cwd=root, home=home, stdin="y\n", ci=True)

        assert "CARRIED" not in " ".join(rendered_commands(root))
        assert not (home / ".vaultspec" / "hook-trust.json").exists()

    def test_the_refusal_names_the_file_and_the_verb(self, tmp_path: Path) -> None:
        root, home = carried_workspace(tmp_path)

        result = run_cli("sync", cwd=root, home=home)

        assert "carried" in (result.stdout + result.stderr).lower()
        assert "spec hooks trust" in result.stdout + result.stderr


class TestApprovalRendersAndRevocationWithdraws:
    """Approval is the whole workflow, and so is taking it back."""

    def test_trust_then_sync_renders_the_hook(self, tmp_path: Path) -> None:
        root, home = carried_workspace(tmp_path)

        approved = run_cli("spec", "hooks", "trust", cwd=root, home=home)
        assert approved.returncode == 0, approved.stdout + approved.stderr

        run_cli("sync", cwd=root, home=home)

        assert "echo CARRIED" in rendered_commands(root)

    def test_revoking_then_syncing_removes_what_was_rendered(
        self, tmp_path: Path
    ) -> None:
        """Revocation has to reach the provider file, not just the ledger.

        The sidecar records exactly what the last sync wrote, so withdrawing a
        grant and syncing again must take the hook back out of the agent's
        configuration. An approval that cannot be undone is not a consent
        mechanism.
        """
        root, home = carried_workspace(tmp_path)
        run_cli("spec", "hooks", "trust", cwd=root, home=home)
        run_cli("sync", cwd=root, home=home)
        assert "echo CARRIED" in rendered_commands(root)

        revoked = run_cli("spec", "hooks", "trust", "--revoke", cwd=root, home=home)
        assert revoked.returncode == 0, revoked.stdout + revoked.stderr

        run_cli("sync", cwd=root, home=home)

        assert "echo CARRIED" not in rendered_commands(root)

    def test_editing_an_approved_hook_withdraws_the_approval(
        self, tmp_path: Path
    ) -> None:
        """Consent is pinned to content, so a pulled change asks again."""
        root, home = carried_workspace(tmp_path)
        run_cli("spec", "hooks", "trust", cwd=root, home=home)
        run_cli("sync", cwd=root, home=home)
        assert "echo CARRIED" in rendered_commands(root)

        (root / ".vaultspec" / "hooks" / "carried.yaml").write_text(
            "event: pre_tool_use\nmatcher: Bash\ncommand: echo REPLACED\n",
            encoding="utf-8",
        )
        run_cli("sync", cwd=root, home=home)

        commands = rendered_commands(root)
        assert "echo REPLACED" not in commands
        assert "echo CARRIED" not in commands


class TestGrantsAreSeparatePerSystem:
    """Approving hooks must not approve triggers, or the reverse."""

    def test_trusting_hooks_does_not_trust_triggers(self, tmp_path: Path) -> None:
        root, home = carried_workspace(tmp_path)
        triggers_dir = root / ".vaultspec" / "triggers"
        triggers_dir.mkdir(parents=True, exist_ok=True)
        (triggers_dir / "lifecycle.yaml").write_text(
            "event: config.synced\nenabled: true\n"
            "actions:\n  - type: shell\n    command: echo TRIGGER\n",
            encoding="utf-8",
        )

        run_cli("spec", "hooks", "trust", cwd=root, home=home)
        listed = run_cli("spec", "triggers", "list", "--json", cwd=root, home=home)

        payload = json.loads(listed.stdout)
        assert payload["data"]["triggers"][0]["trusted"] is False

    def test_hooks_trust_points_at_the_other_verb(self, tmp_path: Path) -> None:
        """The one verb whose meaning changed says where the other grant is."""
        root, home = carried_workspace(tmp_path)
        triggers_dir = root / ".vaultspec" / "triggers"
        triggers_dir.mkdir(parents=True, exist_ok=True)
        (triggers_dir / "lifecycle.yaml").write_text(
            "event: config.synced\nenabled: true\n"
            "actions:\n  - type: shell\n    command: echo TRIGGER\n",
            encoding="utf-8",
        )

        result = run_cli("spec", "hooks", "trust", cwd=root, home=home)

        assert "spec triggers trust" in result.stdout + result.stderr
