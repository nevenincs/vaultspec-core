"""Real-git tests for the ref-scoped vault graph (issue #160).

Exercises :func:`vaultspec_core.graph.refscan.read_vault_at_ref`,
:meth:`vaultspec_core.graph.api.VaultGraph.from_ref`, and the
``vault graph --json --ref`` verb against throwaway git repositories - no
mocks, no fakes, real ``git`` subprocess calls and real blobs.
"""

from __future__ import annotations

import json
import subprocess
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from vaultspec_core.cli import app
from vaultspec_core.graph.api import VaultGraph
from vaultspec_core.graph.cache import cache_path
from vaultspec_core.graph.refscan import RefScanError, read_vault_at_ref

if TYPE_CHECKING:
    from pathlib import Path


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")


def _doc(directory_tag: str, feature: str, title: str, body: str) -> str:
    return (
        f"---\ntags:\n  - '#{directory_tag}'\n  - '#{feature}'\n"
        f"date: '2026-06-13'\n---\n\n# {title}\n\n{body}\n"
    )


@pytest.fixture
def vault_repo(tmp_path) -> tuple[Path, str, str]:
    """A git repo whose ``.vault/`` corpus changes between two commits.

    Returns ``(repo, sha1, sha2)`` where ``sha1`` has two linked documents and
    ``sha2`` adds a third and edits the first.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / ".vault" / "research").mkdir(parents=True)
    (repo / ".vault" / "adr").mkdir(parents=True)

    research = repo / ".vault" / "research" / "2026-06-13-alpha-research.md"
    adr = repo / ".vault" / "adr" / "2026-06-13-alpha-adr.md"

    research.write_text(
        _doc("research", "alpha", "alpha research", "First findings."),
        encoding="utf-8",
    )
    adr.write_text(
        _doc(
            "adr",
            "alpha",
            "alpha adr",
            "Decision grounded in [[2026-06-13-alpha-research]].",
        ),
        encoding="utf-8",
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "c1: alpha research + adr")
    sha1 = _git(repo, "rev-parse", "HEAD")

    # Second commit: add a plan that links the adr, and edit the research body.
    (repo / ".vault" / "plan").mkdir(parents=True)
    plan = repo / ".vault" / "plan" / "2026-06-13-alpha-plan.md"
    plan.write_text(
        _doc("plan", "alpha", "alpha plan", "Plan per [[2026-06-13-alpha-adr]]."),
        encoding="utf-8",
    )
    research.write_text(
        _doc("research", "alpha", "alpha research", "Revised findings, expanded."),
        encoding="utf-8",
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "c2: add plan, revise research")
    sha2 = _git(repo, "rev-parse", "HEAD")

    return repo, sha1, sha2


# ---- read_vault_at_ref ------------------------------------------------------


def test_read_vault_at_ref_returns_corpus_at_each_ref(vault_repo) -> None:
    repo, sha1, sha2 = vault_repo

    at_c1 = dict(read_vault_at_ref(repo, sha1, ".vault"))
    assert set(at_c1) == {
        ".vault/research/2026-06-13-alpha-research.md",
        ".vault/adr/2026-06-13-alpha-adr.md",
    }
    assert "First findings." in at_c1[".vault/research/2026-06-13-alpha-research.md"]

    at_c2 = dict(read_vault_at_ref(repo, sha2, ".vault"))
    assert ".vault/plan/2026-06-13-alpha-plan.md" in at_c2
    # The edit at c2 is visible; the c1 content is not served.
    assert "Revised findings" in at_c2[".vault/research/2026-06-13-alpha-research.md"]


def test_read_vault_at_ref_accepts_branch_name(vault_repo) -> None:
    repo, _sha1, _sha2 = vault_repo
    branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    corpus = read_vault_at_ref(repo, branch, ".vault")
    assert len(corpus) == 3


def test_read_vault_at_ref_unresolvable_ref_raises(vault_repo) -> None:
    repo, _sha1, _sha2 = vault_repo
    with pytest.raises(RefScanError, match="does not resolve"):
        read_vault_at_ref(repo, "no-such-ref", ".vault")


def test_read_vault_at_ref_non_git_raises(tmp_path) -> None:
    not_a_repo = tmp_path / "plain"
    not_a_repo.mkdir()
    with pytest.raises(RefScanError, match="not a git repository"):
        read_vault_at_ref(not_a_repo, "HEAD", ".vault")


# ---- VaultGraph.from_ref ----------------------------------------------------


def test_from_ref_matches_working_tree_build(vault_repo) -> None:
    """A ref build at HEAD is structurally identical to a working-tree build."""
    repo, _sha1, sha2 = vault_repo

    ref_graph = VaultGraph.from_ref(repo, sha2)
    # The working tree equals sha2 (clean), so a no-cache working-tree build is
    # the corpus comparison baseline.
    wt_graph = VaultGraph(repo, use_cache=False)

    assert set(ref_graph.nodes) == set(wt_graph.nodes)
    assert set(ref_graph.digraph.edges()) == set(wt_graph.digraph.edges())
    assert ref_graph.ref == sha2


def test_from_ref_reflects_historical_ref(vault_repo) -> None:
    repo, sha1, _sha2 = vault_repo
    graph = VaultGraph.from_ref(repo, sha1)
    # The plan added at c2 is absent at c1.
    assert "2026-06-13-alpha-plan" not in graph.nodes
    assert "2026-06-13-alpha-adr" in graph.nodes
    # The adr -> research edge declared in the body resolves at c1.
    assert (
        "2026-06-13-alpha-adr",
        "2026-06-13-alpha-research",
    ) in graph.digraph.edges()


def test_from_ref_does_not_write_working_tree_cache(vault_repo) -> None:
    repo, _sha1, sha2 = vault_repo
    VaultGraph.from_ref(repo, sha2)
    assert not cache_path(repo).exists()


def test_from_ref_node_path_is_virtual_tree_path(vault_repo) -> None:
    repo, _sha1, sha2 = vault_repo
    data = VaultGraph.from_ref(repo, sha2).to_dict()
    assert data["ref"] == sha2
    paths = {n["id"]: n["path"] for n in data["nodes"]}
    assert paths["2026-06-13-alpha-adr"] == ".vault/adr/2026-06-13-alpha-adr.md"


def test_working_tree_node_path_is_vault_relative(vault_repo) -> None:
    """A working-tree build emits the same vault-relative path as a ref build.

    Consumer-symmetry follow-up: no absolute OS path leaks into the envelope,
    and both build modes use the identical virtual ``.vault/...`` shape so a
    consumer ingests them through one path format.
    """
    repo, _sha1, sha2 = vault_repo
    wt = VaultGraph(repo, use_cache=False).to_dict()
    paths = {n["id"]: n["path"] for n in wt["nodes"]}
    adr = paths["2026-06-13-alpha-adr"]
    assert adr == ".vault/adr/2026-06-13-alpha-adr.md"
    # No drive letter, no backslash, not absolute: nothing OS-specific leaks.
    assert "\\" not in adr
    assert not adr.startswith("/") and ":" not in adr
    # Identical to the ref-scoped build of the same corpus.
    ref_paths = {
        n["id"]: n["path"] for n in VaultGraph.from_ref(repo, sha2).to_dict()["nodes"]
    }
    assert paths == ref_paths


def test_from_ref_bad_ref_raises(vault_repo) -> None:
    repo, _sha1, _sha2 = vault_repo
    with pytest.raises(RefScanError):
        VaultGraph.from_ref(repo, "nope")


# ---- CLI: vault graph --ref -------------------------------------------------


def test_cli_graph_ref_matches_working_tree(synthetic_project: Path) -> None:
    """``vault graph --json --ref HEAD`` matches the working-tree node set."""
    _init_repo(synthetic_project)
    _git(synthetic_project, "add", "-A")
    _git(synthetic_project, "commit", "-qm", "snapshot")

    runner = CliRunner(env={"NO_COLOR": "1"})
    args = ["--target", str(synthetic_project), "vault", "graph", "--json"]
    ref_result = runner.invoke(app, [*args, "--ref", "HEAD"])
    assert ref_result.exit_code == 0, ref_result.output
    ref_data = json.loads(ref_result.output)["data"]
    assert ref_data["ref"] == "HEAD"

    wt_result = runner.invoke(app, args)
    assert wt_result.exit_code == 0, wt_result.output
    wt_data = json.loads(wt_result.output)["data"]
    assert wt_data["ref"] is None

    ref_nodes = {n["id"] for n in ref_data["nodes"]}
    wt_nodes = {n["id"] for n in wt_data["nodes"]}
    assert ref_nodes == wt_nodes


def test_cli_graph_ref_envelope_is_v2(synthetic_project: Path) -> None:
    _init_repo(synthetic_project)
    _git(synthetic_project, "add", "-A")
    _git(synthetic_project, "commit", "-qm", "snapshot")

    runner = CliRunner(env={"NO_COLOR": "1"})
    args = ["--target", str(synthetic_project), "vault", "graph", "--json"]
    result = runner.invoke(app, [*args, "--ref", "HEAD"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["schema"] == "vaultspec.vault.graph.v2"


def test_cli_graph_unresolvable_ref_exits_nonzero(synthetic_project: Path) -> None:
    _init_repo(synthetic_project)
    _git(synthetic_project, "add", "-A")
    _git(synthetic_project, "commit", "-qm", "snapshot")

    runner = CliRunner(env={"NO_COLOR": "1"})
    result = runner.invoke(
        app,
        [
            "--target",
            str(synthetic_project),
            "vault",
            "graph",
            "--json",
            "--ref",
            "definitely-not-a-ref",
        ],
    )
    assert result.exit_code == 1
    assert "definitely-not-a-ref" in result.output
