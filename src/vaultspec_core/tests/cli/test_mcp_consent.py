"""MCP consent is an explicit terminal decision, enforced for every sync path."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest
from typer.testing import CliRunner

from vaultspec_core.cli import app
from vaultspec_core.core.mcps_definitions import collect_mcp_servers
from vaultspec_core.core.mcps_trust import trust_file_path
from vaultspec_core.core.tests.test_mcps import _init_context
from vaultspec_core.tests.cli.test_hook_consent import run_cli

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.unit


def attended(**_kwargs: object) -> bool:
    """Model terminal streams for the confirmation-only tests."""
    return False


def carried(root: Path) -> Path:
    _init_context(root)
    source = root / ".vaultspec/mcps/server.json"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(
        '{"command":"carried","args":["evil.js"],"env":{"A":"1"}}', encoding="utf-8"
    )
    return source


@pytest.mark.parametrize(
    "args",
    [
        ["spec", "mcps", "sync", "--force"],
        ["sync", "all", "--force"],
        ["install", "claude", "--force"],
    ],
)
def test_unattended_entrypoints_never_enroll_carried_commands(
    tmp_path: Path, args: list[str]
) -> None:
    root = tmp_path / "repo"
    carried(root)
    home = tmp_path / "host"
    home.mkdir()
    result = run_cli(*args, cwd=root, home=home, stdin="y\n")
    assert result.returncode == 0, result.stdout + result.stderr
    target = root / ".mcp.json"
    servers: dict[str, Any] = (
        json.loads(target.read_text(encoding="utf-8")).get("mcpServers", {})
        if target.exists()
        else {}
    )
    assert "server" not in servers
    assert not (home / ".vaultspec/mcp-trust.json").exists()


@pytest.mark.parametrize("json_output", [False, True])
def test_piped_yes_cannot_approve(tmp_path: Path, json_output: bool) -> None:
    carried(tmp_path)
    args = ["spec", "mcps", "trust", "--target", str(tmp_path)]
    if json_output:
        args.append("--json")
    result = CliRunner().invoke(app, args, input="y\n")
    assert result.exit_code == 1
    assert "interactive terminal" in result.output
    assert not trust_file_path().exists()
    if json_output:
        assert json.loads(result.stdout)["status"] == "failed"


@pytest.mark.parametrize("answer", ["y\n", "n\n", "", "\x03"])
def test_terminal_confirmation_is_required(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, answer: str
) -> None:
    carried(tmp_path)
    monkeypatch.setattr("vaultspec_core.config.is_unattended", attended)
    runner = CliRunner()
    result = runner.invoke(
        app, ["spec", "mcps", "trust", "--target", str(tmp_path)], input=answer
    )
    assert '"command": "carried"' in result.output
    assert '"args": [' in result.output
    assert '"env": {' in result.output
    assert '"provider": "claude"' in result.output
    assert trust_file_path().exists() is (answer == "y\n")
    assert not (tmp_path / ".mcp.json").exists()
    synced = runner.invoke(
        app, ["spec", "mcps", "sync", "--json", "--target", str(tmp_path)]
    )
    assert synced.exit_code == 0
    assert (tmp_path / ".mcp.json").exists() is (answer == "y\n")


def test_file_changed_while_operator_reviews_is_not_approved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = carried(tmp_path)
    monkeypatch.setattr("vaultspec_core.config.is_unattended", attended)

    def confirm(*_args: object, **_kwargs: object) -> bool:
        source.write_text('{"command":"changed-after-display"}', encoding="utf-8")
        return True

    monkeypatch.setattr("typer.confirm", confirm)
    runner = CliRunner()
    approved = runner.invoke(app, ["spec", "mcps", "trust", "--target", str(tmp_path)])
    assert approved.exit_code == 0
    synced = runner.invoke(
        app, ["spec", "mcps", "sync", "--force", "--target", str(tmp_path)]
    )
    assert synced.exit_code == 0
    assert not (tmp_path / ".mcp.json").exists()
    assert "not approved" in synced.output


def test_repository_warnings_cannot_erase_approval_display(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    carried(tmp_path)
    monkeypatch.setattr("vaultspec_core.config.is_unattended", attended)

    def collect(
        warnings: list[str] | None = None, **kwargs: Any
    ) -> dict[str, tuple[Path, dict[str, Any]]]:
        # POSIX permits these bytes in filenames; inject its parse-warning
        # representation so the UI regression is portable to Windows too.
        if warnings is not None:
            warnings.append("Invalid definition \x1b[2J\x1b[Hhidden.json")
        return collect_mcp_servers(warnings=warnings, **kwargs)

    monkeypatch.setattr(
        "vaultspec_core.core.mcps_definitions.collect_mcp_servers", collect
    )
    result = CliRunner().invoke(
        app,
        ["spec", "mcps", "trust", "--target", str(tmp_path)],
        input="y\n",
        color=True,
    )
    assert result.exit_code == 0
    assert "\x1b[2J" not in result.stderr
    assert r"\u001b[2J" in result.stderr
    assert '"command": "carried"' in result.stdout


def test_split_source_approval_matches_top_level_sync(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "destination"
    carried(source)
    carried(target).write_text('{"command":"destination-only"}', encoding="utf-8")
    monkeypatch.chdir(source)
    monkeypatch.setattr("vaultspec_core.config.is_unattended", attended)
    runner = CliRunner()
    args = ["spec", "mcps", "trust", "--target", str(target)]
    assert runner.invoke(app, args, input="y\n").exit_code == 0
    synced = runner.invoke(app, ["sync", "claude", "--target", str(target)])
    assert synced.exit_code == 0, synced.output
    assert not (target / ".mcp.json").exists()
    approval = runner.invoke(app, [*args, "--source-from-cwd"], input="y\n")
    assert approval.exit_code == 0, approval.output
    assert '"command": "carried"' in approval.output
    synced = runner.invoke(app, ["sync", "claude", "--target", str(target)])
    assert synced.exit_code == 0, synced.output
    servers = json.loads((target / ".mcp.json").read_text(encoding="utf-8"))[
        "mcpServers"
    ]
    assert servers["server"]["command"] == "carried"
