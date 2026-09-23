"""``vaultspec-core commit-gate`` as a commit hook runs it.

Each test drives the real CLI in a subprocess from the workspace root, against
a real install and a real git index, which is exactly how the hook runner
invokes it. No test doubles.
"""

from __future__ import annotations

import json
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
_CLEAN = (
    "---\ntags:\n  - '#research'\n  - '#alpha'\ndate: '2026-01-01'\n"
    "modified: '2026-01-01'\nrelated: []\n---\n\n"
    "# `alpha` research: `topic`\n\nProse.\n"
)
# Commands that rewrite documents beyond the one a finding names. A gate's
# output must never propose them.
_MUTATING_ADVICE = ("repair", "--fix", "sanitize")


def _git(root: Path, *args: str) -> None:
    null = "NUL" if os.name == "nt" else "/dev/null"
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "vaultspec-test",
        "GIT_AUTHOR_EMAIL": "test@vaultspec.local",
        "GIT_COMMITTER_NAME": "vaultspec-test",
        "GIT_COMMITTER_EMAIL": "test@vaultspec.local",
        "GIT_CONFIG_GLOBAL": null,
        "GIT_CONFIG_SYSTEM": null,
        "HOME": str(root),
    }
    subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, env=env, check=True
    )


def _gate(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "vaultspec_core", "commit-gate", *args],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _write(root: Path, text: str) -> None:
    path = root / _DOC
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


@pytest.fixture
def repo(factory: WorkspaceFactory) -> Path:
    root = factory.root
    _git(root, "init", "-q", "-b", "main")
    factory.install()
    _write(root, _CLEAN)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "seed")
    return root


def test_a_clean_staged_change_passes(repo: Path) -> None:
    _write(repo, _CLEAN + "\nMore prose.\n")
    _git(repo, "add", _DOC)

    result = _gate(repo, _DOC)

    assert result.returncode == 0, result.stderr


def test_an_introduced_error_blocks_without_mutating_advice(repo: Path) -> None:
    _write(repo, _CLEAN + "\nSee [[nowhere-doc]] here.\n")
    _git(repo, "add", _DOC)

    result = _gate(repo, _DOC)

    assert result.returncode == 1
    assert "Dangling wiki-link: [[nowhere-doc]] does not exist" in result.stderr
    output = (result.stdout + result.stderr).lower()
    for advice in _MUTATING_ADVICE:
        assert advice not in output, advice


def test_with_no_paths_the_staged_files_are_read_from_git(repo: Path) -> None:
    _write(repo, _CLEAN + "\nSee [[nowhere-doc]] here.\n")
    _git(repo, "add", _DOC)

    assert _gate(repo).returncode == 1


def test_an_unstaged_defect_is_not_the_commits_business(repo: Path) -> None:
    _write(repo, _CLEAN + "\nSee [[nowhere-doc]] here.\n")

    assert _gate(repo).returncode == 0


def test_a_staged_per_machine_file_blocks(repo: Path) -> None:
    _git(repo, "add", "-f", "--", ".vaultspec/providers.json")

    result = _gate(repo)

    assert result.returncode == 1
    assert ".vaultspec/providers.json" in result.stderr
    assert "git restore --staged" in result.stderr


def test_json_reports_one_envelope_with_the_blocking_findings(repo: Path) -> None:
    _write(repo, _CLEAN + "\nSee [[nowhere-doc]] here.\n")
    _git(repo, "add", _DOC)

    result = _gate(repo, _DOC, "--json")

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "failed"
    checks = {finding["check"] for finding in payload["data"]["blocking"]}
    assert "dangling" in checks


def test_outside_a_workspace_the_gate_passes_quietly(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    _git(root, "init", "-q", "-b", "main")

    result = _gate(root)

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""
