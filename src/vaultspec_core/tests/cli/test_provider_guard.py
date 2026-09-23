"""The provider guard blocks per-machine files and nothing a team shares.

The guard used to block ``CLAUDE.md``, ``.mcp.json`` and every provider
directory, which the sharing policy commits so teammates inherit the project's
rules, and it advised untracking them. These tests drive a real install, a real
``sync`` and a real ``git`` index; no test doubles.
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.core.commands import check_staged_provider_artifacts

if TYPE_CHECKING:
    from pathlib import Path

    from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory

pytestmark = [pytest.mark.integration]


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    null = "NUL" if os.name == "nt" else "/dev/null"
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "vaultspec-test",
        "GIT_AUTHOR_EMAIL": "test@vaultspec.local",
        "GIT_COMMITTER_NAME": "vaultspec-test",
        "GIT_COMMITTER_EMAIL": "test@vaultspec.local",
        "GIT_CONFIG_GLOBAL": null,
        "GIT_CONFIG_SYSTEM": null,
        "HOME": str(cwd),
    }
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )


@pytest.fixture
def committed(factory: WorkspaceFactory) -> WorkspaceFactory:
    """An installed consumer workspace with everything committed."""
    _git(factory.root, "init", "-q", "-b", "main")
    factory.install()
    _git(factory.root, "add", "-A")
    _git(factory.root, "commit", "-q", "-m", "install")
    return factory


def test_a_new_team_rule_and_its_projections_pass(committed: WorkspaceFactory) -> None:
    root = committed.root
    (root / ".vaultspec" / "rules" / "team.md").write_text(
        "---\nname: team\n---\nShared team rule.\n", encoding="utf-8"
    )
    committed.sync()
    _git(root, "add", "-A")
    staged = _git(root, "diff", "--cached", "--name-only").stdout.splitlines()
    assert ".claude/rules/team.md" in staged
    assert "CLAUDE.md" in staged

    assert check_staged_provider_artifacts(cwd=root) == []


def test_shared_root_files_pass(committed: WorkspaceFactory) -> None:
    root = committed.root
    for name in ("CLAUDE.md", ".mcp.json"):
        with (root / name).open("a", encoding="utf-8") as fh:
            fh.write("\n")
        _git(root, "add", name)

    assert check_staged_provider_artifacts(cwd=root) == []


@pytest.mark.parametrize(
    "path",
    [
        ".vaultspec/providers.json",
        ".gitignore.lock",
        ".vaultspec/stray.lock",
        ".vaultspec/_snapshots/x.json",
        ".vault/data/.graph-cache/graph.json",
    ],
)
def test_per_machine_files_are_blocked(committed: WorkspaceFactory, path: str) -> None:
    root = committed.root
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("{}", encoding="utf-8")
    _git(root, "add", "-f", "--", path)

    assert path in check_staged_provider_artifacts(cwd=root)


def test_failure_advises_unstaging_never_untracking(
    committed: WorkspaceFactory,
) -> None:
    root = committed.root
    _git(root, "add", "-f", "--", ".vaultspec/providers.json")

    result = subprocess.run(
        [sys.executable, "-m", "vaultspec_core", "check-providers"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert result.returncode == 1
    assert "git restore --staged" in result.stderr
    assert "rm --cached" not in result.stderr


def test_a_declined_workspaces_own_hook_config_is_not_per_machine(
    committed: WorkspaceFactory,
) -> None:
    """Declining vaultspec's hooks makes the block ignore the config name.

    That keeps vaultspec's refused config out of a sweeping commit. A config
    the operator deliberately authors and stages there is theirs, not a
    per-machine artifact, so the guard must let it through.
    """
    from vaultspec_core.core.workspace_mode import (
        HooksDeclaration,
        write_hooks_declaration,
    )

    root = committed.root
    write_hooks_declaration(root, HooksDeclaration(pre_commit=False))
    (root / ".pre-commit-config.yaml").write_text("repos: []\n", encoding="utf-8")
    _git(root, "add", "-f", "--", ".pre-commit-config.yaml")

    assert check_staged_provider_artifacts(cwd=root) == []
