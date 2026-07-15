"""Real Claude Code and Codex CLI acceptance for native MCP enrollment."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from vaultspec_core.config import reset_config
from vaultspec_core.core.commands import install_run
from vaultspec_core.core.mcps import mcp_uninstall

pytestmark = pytest.mark.integration


def _host_executable(name: str) -> str:
    candidates = (f"{name}.cmd", f"{name}.exe", name)
    executable = next(
        (
            shutil.which(candidate)
            for candidate in candidates
            if shutil.which(candidate)
        ),
        None,
    )
    assert executable is not None, f"Release acceptance requires the real {name} CLI"
    return executable


def _isolated_env(root: Path) -> dict[str, str]:
    home = root / "home"
    codex_home = root / "codex-home"
    home.mkdir(parents=True)
    codex_home.mkdir(parents=True)
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["USERPROFILE"] = str(home)
    env["CODEX_HOME"] = str(codex_home)
    return env


def _run(
    command: list[str], *, cwd: Path, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=30,
    )


def _run_core(
    project: Path, env: dict[str, str], *args: str
) -> subprocess.CompletedProcess[str]:
    return _run(
        [sys.executable, "-m", "vaultspec_core", "--target", str(project), *args],
        cwd=project,
        env=env,
    )


def _install_all(project: Path) -> None:
    project.mkdir()
    reset_config()
    install_run(
        path=project,
        provider="all",
        upgrade=False,
        dry_run=False,
        force=False,
    )


def _trust_codex_project(project: Path, env: dict[str, str]) -> None:
    codex_home = Path(env["CODEX_HOME"])
    project_key = str(project.resolve()).lower().replace("'", "''")
    (codex_home / "config.toml").write_text(
        f"[projects.'{project_key}']\ntrust_level = \"trusted\"\n",
        encoding="utf-8",
    )


def test_real_hosts_recognize_project_enrollment(tmp_path: Path) -> None:
    project = tmp_path / "project"
    env = _isolated_env(tmp_path)
    _install_all(project)
    _trust_codex_project(project, env)

    claude = _run(
        [_host_executable("claude"), "mcp", "get", "vaultspec-core"],
        cwd=project,
        env=env,
    )
    assert claude.returncode == 0, claude.stdout + claude.stderr
    assert "vaultspec-core" in claude.stdout
    assert "Pending approval" in claude.stdout

    codex = _run(
        [
            _host_executable("codex"),
            "-C",
            str(project),
            "mcp",
            "get",
            "vaultspec-core",
            "--json",
        ],
        cwd=project,
        env=env,
    )
    assert codex.returncode == 0, codex.stdout + codex.stderr
    payload = json.loads(codex.stdout)
    assert payload["name"] == "vaultspec-core"
    assert payload["transport"]["type"] == "stdio"


def test_real_hosts_recognize_isolated_user_enrollment(tmp_path: Path) -> None:
    project = tmp_path / "project"
    env = _isolated_env(tmp_path)
    _install_all(project)
    mcp_uninstall(project, provider="all")

    for provider in ("claude", "codex"):
        result = _run_core(
            project,
            env,
            "spec",
            "mcps",
            "sync",
            provider,
            "--scope",
            "user",
            "--json",
        )
        assert result.returncode == 0, result.stdout + result.stderr

    claude = _run(
        [_host_executable("claude"), "mcp", "get", "vaultspec-core"],
        cwd=project,
        env=env,
    )
    assert claude.returncode == 0, claude.stdout + claude.stderr
    assert "User config" in claude.stdout

    codex = _run(
        [_host_executable("codex"), "mcp", "get", "vaultspec-core", "--json"],
        cwd=project,
        env=env,
    )
    assert codex.returncode == 0, codex.stdout + codex.stderr
    assert json.loads(codex.stdout)["name"] == "vaultspec-core"


def test_claude_local_is_recognized_and_codex_local_is_rejected(tmp_path: Path) -> None:
    project = tmp_path / "project"
    env = _isolated_env(tmp_path)
    _install_all(project)
    mcp_uninstall(project, provider="all")

    claude_sync = _run_core(
        project,
        env,
        "spec",
        "mcps",
        "sync",
        "claude",
        "--scope",
        "local",
        "--json",
    )
    assert claude_sync.returncode == 0, claude_sync.stdout + claude_sync.stderr
    claude = _run(
        [_host_executable("claude"), "mcp", "get", "vaultspec-core"],
        cwd=project,
        env=env,
    )
    assert claude.returncode == 0, claude.stdout + claude.stderr
    assert "Local config" in claude.stdout

    codex_sync = _run_core(
        project,
        env,
        "spec",
        "mcps",
        "sync",
        "codex",
        "--scope",
        "local",
        "--json",
    )
    assert codex_sync.returncode == 1
    assert "distinct local MCP scope" in codex_sync.stdout
    assert not (Path(env["CODEX_HOME"]) / "config.toml").exists()
