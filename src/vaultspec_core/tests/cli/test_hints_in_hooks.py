"""Next-step hints never propose a vault-wide rewrite to a commit hook.

A commit hook's failure output is often acted on without review. A hook that
still runs ``vault check all`` (a hand-written or not yet migrated entry) must
not end a failed commit by proposing ``vault repair``, which rewrites documents
the commit never touched. Each test drives the real CLI in a subprocess against
a real git repository; the hook test runs it from a real git pre-commit hook.
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory

pytestmark = [pytest.mark.integration]

_DOC = ".vault/research/2026-01-01-alpha-research.md"
_BROKEN = (
    "---\ntags:\n  - '#research'\n  - '#alpha'\ndate: '2026-01-01'\n"
    "modified: '2026-01-01'\nrelated: []\n---\n\n"
    "# `alpha` research: `topic`\n\nSee [[nowhere-doc]] here.\n"
)


def _git_env(root: Path) -> dict[str, str]:
    null = "NUL" if os.name == "nt" else "/dev/null"
    return {
        **os.environ,
        "GIT_AUTHOR_NAME": "vaultspec-test",
        "GIT_AUTHOR_EMAIL": "test@vaultspec.local",
        "GIT_COMMITTER_NAME": "vaultspec-test",
        "GIT_COMMITTER_EMAIL": "test@vaultspec.local",
        "GIT_CONFIG_GLOBAL": null,
        "GIT_CONFIG_SYSTEM": null,
        "HOME": str(root),
    }


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_git_env(root),
        check=False,
    )


def _check_all(root: Path, **env: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "vaultspec_core", "vault", "check", "all"],
        cwd=root,
        env={**os.environ, **env},
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


@pytest.fixture
def broken_repo(factory: WorkspaceFactory) -> Path:
    root = factory.root
    _git(root, "init", "-q", "-b", "main")
    factory.install()
    path = root / _DOC
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_BROKEN, encoding="utf-8", newline="\n")
    return root


def test_a_commit_hooks_git_index_file_suppresses_hints(broken_repo: Path) -> None:
    result = _check_all(broken_repo, GIT_INDEX_FILE=".git/index")

    assert result.returncode == 1, result.stdout
    assert "Next action" not in result.stdout
    assert "vault repair" not in result.stdout
    assert "--fix" not in result.stdout


def test_a_failed_check_proposes_only_a_repair_preview(broken_repo: Path) -> None:
    result = _check_all(broken_repo)

    assert result.returncode == 1, result.stdout
    assert "vaultspec-core vault repair --dry-run" in result.stdout
    assert "vaultspec-core vault repair\n" not in result.stdout
    # Outside a hook the auto-fix suggestion still prints, so the hook tests'
    # absence assertions are about the hook and not about this document.
    assert "--fix" in result.stdout


def test_a_failed_check_in_a_commit_hook_proposes_no_follow_up(
    broken_repo: Path,
) -> None:
    python = sys.executable.replace("\\", "/")
    hook = broken_repo / ".git" / "hooks" / "pre-commit"
    hook.write_text(
        f'#!/bin/sh\n"{python}" -m vaultspec_core vault check all\n',
        encoding="utf-8",
        newline="\n",
    )
    hook.chmod(0o755)
    _git(broken_repo, "add", _DOC)

    result = _git(broken_repo, "commit", "-q", "-m", "broken")

    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert "Dangling wiki-link" in output or "nowhere-doc" in output, output
    assert "Next action" not in output
    assert "vault repair" not in output
    assert "--fix" not in output
