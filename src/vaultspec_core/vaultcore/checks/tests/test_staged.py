"""The staged pass agrees with the combined pass on the documents it checks.

A commit gate that checks only staged documents is only trustworthy if, for
those documents, it reports exactly what the whole-corpus pass would. These
tests build a real synthetic vault seeded with every pathology the generator
knows, run both passes, and compare per checker. No mocks or patches.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from ....config import reset_config
from ....testing.synthetic import PATHOLOGY_NAMES, build_synthetic_vault
from ...scanner import scan_vault
from .. import run_all_checks
from ..staged import DOCUMENT_CHECK_NAMES, check_staged_documents

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from .._base import CheckResult

pytestmark = [pytest.mark.unit]


@pytest.fixture(autouse=True)
def reset_cfg() -> Generator[None]:
    reset_config()
    yield
    reset_config()


def _seed_document_defects(root: Path) -> None:
    """Give the checkers the generator's pathologies miss something to find.

    One document each gains a leftover template comment, surplus blank lines,
    an unreplaced placeholder, a ``.md`` wiki-link, and a declared body schema
    it does not satisfy; one more file is not valid UTF-8.
    """
    adrs = sorted((root / ".vault" / "adr").glob("*.md"))
    plans = sorted((root / ".vault" / "plan").glob("*.md"))
    first, second = adrs[0], adrs[1]
    with first.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write("\n<!-- leftover template guidance -->\n\n\n\n\nTrailing prose.\n")
    with plans[0].open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(f"\nSee {{feature}} and [[{plans[1].stem}.md]].\n")
    text = second.read_text(encoding="utf-8")
    second.write_text(
        text.replace("\ndate:", "\nbody_schema: 'body-v1'\ndate:", 1),
        encoding="utf-8",
        newline="\n",
    )
    # A qualified link resolves only to a stem shared by several documents; the
    # same form naming a unique stem is dangling, exactly as in the graph.
    collision = next((root / ".vault" / "plan").glob("*collision-shared-stem.md"))
    unique_adr = adrs[2].stem
    collision.write_text(
        collision.read_text(encoding="utf-8").replace(
            "related: []",
            f'related:\n  - "[[adr/{collision.stem}]]"\n  - "[[adr/{unique_adr}]]"',
            1,
        ),
        encoding="utf-8",
        newline="\n",
    )
    (root / ".vault" / "adr" / "2026-01-09-encoding-broken-adr.md").write_bytes(
        b"---\ntags: []\n---\n\xff\xfe not utf-8\n"
    )


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    root = tmp_path.resolve()
    build_synthetic_vault(root, n_docs=48, seed=11, pathologies=sorted(PATHOLOGY_NAMES))
    _seed_document_defects(root)
    return root


def _findings(results: list[CheckResult], name: str, scope: set[Path]) -> set[tuple]:
    (result,) = [r for r in results if r.check_name == name]
    return {
        (d.path, d.message, d.severity) for d in result.diagnostics if d.path in scope
    }


def test_results_follow_the_declared_checker_order(vault: Path) -> None:
    results = check_staged_documents(vault, [])

    assert tuple(r.check_name for r in results) == DOCUMENT_CHECK_NAMES


def test_subset_findings_match_the_combined_pass(vault: Path) -> None:
    documents = sorted(scan_vault(vault))
    subset = documents[::2]
    scope = {path.relative_to(vault) for path in subset}

    full = run_all_checks(vault)
    staged = check_staged_documents(vault, subset)

    compared = 0
    for name in DOCUMENT_CHECK_NAMES:
        expected = _findings(full, name, scope)
        assert _findings(staged, name, scope) == expected, name
        compared += len(expected)
    # Guard against a vacuous pass: the pathologies must reach the subset.
    assert compared > 0


def test_every_document_matches_when_all_are_staged(vault: Path) -> None:
    documents = sorted(scan_vault(vault))
    scope = {path.relative_to(vault) for path in documents}

    full = run_all_checks(vault)
    staged = check_staged_documents(vault, documents)

    for name in DOCUMENT_CHECK_NAMES:
        expected = _findings(full, name, scope)
        # Every admitted checker must have findings here, or its agreement
        # with the combined pass is untested.
        assert expected, f"{name} found nothing to compare"
        assert _findings(staged, name, scope) == expected, name


def test_non_vault_and_missing_paths_are_ignored(vault: Path) -> None:
    (vault / "README.md").write_text("# readme [[nowhere]]\n", encoding="utf-8")

    results = check_staged_documents(
        vault, ["README.md", ".vault/adr/deleted-in-this-commit.md", "src/x.py"]
    )

    assert all(not r.diagnostics for r in results)


def test_the_pass_never_writes(vault: Path) -> None:
    documents = sorted(scan_vault(vault))
    before = {path: path.read_bytes() for path in documents}

    check_staged_documents(vault, documents)

    assert {path: path.read_bytes() for path in documents} == before
