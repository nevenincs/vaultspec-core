"""Installation lifecycle keeps private values out of all public surfaces."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from typer.testing import CliRunner, Result

from vaultspec_core.cli import app
from vaultspec_core.config import VAULTSPEC_CORE_TYPESAFE_API_KEY as KEY
from vaultspec_core.config.credential import CredentialSource, resolve_credential
from vaultspec_core.config.local_env import LOCAL_ENV, read_local_environment

pytestmark = [pytest.mark.integration]
FAKE_KEY = "fake-install-key-for-tests"
HINTS = "VAULTSPEC_NO_HINTS"


def _install(runner: CliRunner, root: Path, *args: str) -> Result:
    return runner.invoke(
        app,
        [
            "--target",
            str(root),
            "install",
            "codex",
            "--skip",
            "precommit",
            "--skip",
            "hooks",
            "--json",
            *args,
        ],
        env={KEY.env_name: FAKE_KEY},
    )


def test_install_upgrade_force_sync_and_replacement(
    tmp_path: Path, runner: CliRunner
) -> None:
    first = _install(runner, tmp_path, "--env", KEY.env_name, "--env", f"{HINTS}=1")
    assert first.exit_code == 0, first.output
    assert FAKE_KEY not in first.output
    assert json.loads(first.output)["data"]["environment"][KEY.env_name] == "created"
    before = (tmp_path / LOCAL_ENV).read_bytes()
    disabled = runner.invoke(
        app, ["--target", str(tmp_path), "spec", "gitignore", "disable", "--json"]
    )
    assert disabled.exit_code == 0, disabled.output
    assert read_local_environment(tmp_path)[KEY.env_name] == FAKE_KEY
    for flags in (("--upgrade",), ("--force",), ("--upgrade", "--mode", "dev")):
        if "dev" in flags:
            (tmp_path / "pyproject.toml").write_text(
                '[project]\nname="test-env"\nversion="0.1.0"\n'
            )
        result = _install(runner, tmp_path, *flags)
        assert result.exit_code == 0, result.output
        assert (tmp_path / LOCAL_ENV).read_bytes() == before
        assert FAKE_KEY not in result.output
    result = runner.invoke(
        app,
        [
            "--target",
            str(tmp_path),
            "sync",
            "codex",
            "--skip",
            "precommit",
            "--skip",
            "hooks",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / LOCAL_ENV).read_bytes() == before
    changed = _install(runner, tmp_path, "--upgrade", "--env", f"{HINTS}=0")
    assert changed.exit_code == 0, changed.output
    assert read_local_environment(tmp_path) == {KEY.env_name: FAKE_KEY, HINTS: "0"}
    credential = resolve_credential(KEY, tmp_path, {})
    assert credential is not None and credential.source is CredentialSource.LOCAL_ENV
    for path in tmp_path.rglob("*"):
        if path.is_file() and path != tmp_path / LOCAL_ENV:
            assert FAKE_KEY.encode() not in path.read_bytes(), path


def test_env_file_dry_run_and_secret_argument_redaction(
    tmp_path: Path, runner: CliRunner
) -> None:
    source = tmp_path / "input.env"
    source.write_text(f"{KEY.env_name}={FAKE_KEY}\n{HINTS}=1\n")
    target = tmp_path / "new-project"
    preview = _install(
        runner, target, "--env-file", str(source), "--env", f"{HINTS}=0", "--dry-run"
    )
    assert preview.exit_code == 0, preview.output
    assert not target.exists()
    assert FAKE_KEY not in preview.output
    bad = _install(runner, target, "--env", f"{KEY.env_name}={FAKE_KEY}")
    assert bad.exit_code == 1
    assert FAKE_KEY not in bad.output
    assert not target.exists()
    installed = _install(
        runner, target, "--env-file", str(source), "--env", f"{HINTS}=0"
    )
    assert installed.exit_code == 0, installed.output
    assert read_local_environment(target) == {KEY.env_name: FAKE_KEY, HINTS: "0"}


def test_failed_install_preserves_existing_settings(
    tmp_path: Path, runner: CliRunner
) -> None:
    assert _install(runner, tmp_path, "--env", KEY.env_name).exit_code == 0
    before = (tmp_path / LOCAL_ENV).read_bytes()
    failed = _install(runner, tmp_path, "--mode", "dependency", "--env", f"{HINTS}=1")
    assert failed.exit_code != 0
    assert (tmp_path / LOCAL_ENV).read_bytes() == before
    assert FAKE_KEY not in failed.output
    (tmp_path / ".mcp.json").write_text("not valid JSON")
    failed = runner.invoke(
        app,
        [
            "--target",
            str(tmp_path),
            "install",
            "claude",
            "--force",
            "--json",
            "--env",
            f"{HINTS}=1",
            "--skip",
            "precommit",
            "--skip",
            "hooks",
        ],
    )
    assert failed.exit_code == 1, failed.output
    assert "MCP provider-native enrollment failed" in failed.output
    assert (tmp_path / LOCAL_ENV).read_bytes() == before


def test_unsafe_settings_still_produce_value_free_json_errors(
    tmp_path: Path,
    runner: CliRunner,
) -> None:
    (tmp_path / ".vaultspec").mkdir()
    (tmp_path / LOCAL_ENV).write_text(f"{KEY.env_name}={FAKE_KEY}\n")
    result = _install(runner, tmp_path, "--env", "unsupported")
    assert result.exit_code == 1, result.output
    assert json.loads(result.stdout)["status"] == "failed"
    assert FAKE_KEY not in result.output
