"""The commit gate blocks only on errors the commit introduces.

An author must never be stopped by a defect a document already carried when
they opened it, and must always be stopped by one they add. These tests commit
real documents in a real repository, change them, and ask the gate what
blocks. No mocks or patches.
"""

from __future__ import annotations

import os
import subprocess
from typing import TYPE_CHECKING

import pytest

from ....config import reset_config
from ..staged import gate_staged_documents

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

pytestmark = [pytest.mark.integration]

_DOC = ".vault/research/2026-01-01-alpha-research.md"
_CLEAN = (
    "---\ntags:\n  - '#research'\n  - '#alpha'\ndate: '2026-01-01'\n"
    "modified: '2026-01-01'\nrelated: []\n---\n\n"
    "# `alpha` research: `topic`\n\nProse.\n"
)


@pytest.fixture(autouse=True)
def reset_cfg() -> Generator[None]:
    reset_config()
    yield
    reset_config()


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


def _write(root: Path, text: str) -> None:
    path = root / _DOC
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path.resolve()
    _git(root, "init", "-q", "-b", "main")
    return root


def _commit(root: Path, text: str) -> None:
    _write(root, text)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "seed")


def _blocking_messages(root: Path) -> list[str]:
    outcome = gate_staged_documents(root, [_DOC])
    return [diagnostic.message for _name, diagnostic in outcome.blocking]


def test_a_clean_change_does_not_block(repo: Path) -> None:
    _commit(repo, _CLEAN)
    _write(repo, _CLEAN + "\nMore prose.\n")

    assert _blocking_messages(repo) == []


def test_an_inherited_error_is_reported_but_does_not_block(repo: Path) -> None:
    _commit(repo, _CLEAN + "\nSee [[nowhere-doc]] here.\n")
    _write(repo, _CLEAN + "\nSee [[nowhere-doc]] here.\n\nMore prose.\n")

    outcome = gate_staged_documents(repo, [_DOC])

    assert outcome.blocking == []
    reported = [d.message for r in outcome.results for d in r.diagnostics]
    assert "Dangling wiki-link: [[nowhere-doc]] does not exist" in reported


def test_an_introduced_error_blocks(repo: Path) -> None:
    _commit(repo, _CLEAN)
    _write(repo, _CLEAN + "\nSee [[nowhere-doc]] here.\n")

    assert "Dangling wiki-link: [[nowhere-doc]] does not exist" in (
        _blocking_messages(repo)
    )


def test_a_new_document_answers_for_all_its_errors(repo: Path) -> None:
    _commit(repo, _CLEAN)
    other = ".vault/research/2026-01-02-beta-research.md"
    (repo / other).write_text(
        _CLEAN.replace("#alpha", "#beta").replace("alpha", "beta")
        + "\nUnreplaced {feature} here.\n",
        encoding="utf-8",
        newline="\n",
    )

    outcome = gate_staged_documents(repo, [other])

    assert [name for name, _d in outcome.blocking] == ["placeholders"]


def test_a_first_commit_has_nothing_to_inherit(repo: Path) -> None:
    _write(repo, _CLEAN + "\nSee [[nowhere-doc]] here.\n")

    assert "Dangling wiki-link: [[nowhere-doc]] does not exist" in (
        _blocking_messages(repo)
    )


def test_a_warning_never_blocks(repo: Path) -> None:
    _commit(repo, _CLEAN)
    _write(repo, _CLEAN + "\n<!-- leftover template guidance -->\n")

    outcome = gate_staged_documents(repo, [_DOC])

    assert outcome.blocking == []
    assert any(r.check_name == "annotations" and r.diagnostics for r in outcome.results)


def test_a_path_that_was_a_directory_does_not_cost_its_neighbours_their_baseline(
    repo: Path,
) -> None:
    """A staged path that is a tree at HEAD must not desynchronise the others.

    The object database answers every requested path in order; a tree's
    listing sits in the same stream as the blobs after it, and misreading its
    length would match later documents against the wrong bytes.
    """
    inherited = _CLEAN + "\nSee [[nowhere-doc]] here.\n"
    folder = repo / ".vault" / "research" / "0-folder.md"
    folder.mkdir(parents=True)
    (folder / "inner.txt").write_text("inside a directory\n", encoding="utf-8")
    _commit(repo, inherited)

    for child in folder.iterdir():
        child.unlink()
    folder.rmdir()
    folder.write_text(_CLEAN.replace("alpha", "zero"), encoding="utf-8")
    _write(repo, inherited + "\nMore prose.\n")

    import pathlib

    outcome = gate_staged_documents(repo, [".vault/research/0-folder.md", _DOC])

    assert [d for _n, d in outcome.blocking if d.path == pathlib.Path(_DOC)] == []


def test_the_baseline_pass_never_writes(repo: Path) -> None:
    _commit(repo, _CLEAN + "\nSee [[nowhere-doc]] here.\n")
    _write(repo, _CLEAN + "\nSee [[nowhere-doc]] here.\n\nMore prose.\n")
    before = {
        p: p.read_bytes()
        for p in repo.rglob("*")
        if p.is_file() and ".git" not in p.parts
    }

    gate_staged_documents(repo, [_DOC])

    after = {
        p: p.read_bytes()
        for p in repo.rglob("*")
        if p.is_file() and ".git" not in p.parts
    }
    assert after == before
