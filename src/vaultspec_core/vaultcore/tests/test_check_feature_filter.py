"""The ``--feature`` filter in the text-scanning checkers.

``check_annotations`` and ``check_markdown`` parsed every document's
frontmatter to answer one question: does this document carry the feature the
pass is restricted to. On an unrestricted pass - what ``vault check all`` runs
- the answer was never consulted, so 4,739 metadata parses per run were
discarded. The parse now happens only when a feature was actually named.

That moved the parse inside a conditional, and nothing in the suite exercised
either checker with a feature set, so a mistake there would have been silent:
the unrestricted path would still look perfect while the filter reported the
whole corpus. These tests pin both directions - the named feature's documents
are reported, every other feature's are not, and an unrestricted pass still
reports them all.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]

#: A body carrying both a template annotation and markdown-hygiene damage
#: (trailing whitespace and a doubled blank line), so one fixture serves both
#: checkers.
_DIRTY_BODY = (
    "# {title}\n\n<!-- TEMPLATE: replace this -->\n\ntrailing space   \n\n\n\nend\n"
)


def _write_doc(root: Path, feature: str, index: int) -> Path:
    """Write one research document for *feature* with findable damage."""
    path = root / ".vault" / "research" / f"2026-07-0{index}-{feature}-research.md"
    path.write_text(
        "---\n"
        "tags:\n"
        "  - '#research'\n"
        f"  - '#{feature}'\n"
        f"date: '2026-07-0{index}'\n"
        f"modified: '2026-07-0{index}'\n"
        "related: []\n"
        "---\n\n" + _DIRTY_BODY,
        encoding="utf-8",
    )
    return path


@pytest.fixture
def two_feature_vault(tmp_path: Path) -> Path:
    """A workspace with one damaged document under each of two features."""
    root = tmp_path / "filtered"
    root.mkdir()
    WorkspaceFactory(root).install()
    _write_doc(root, "alpha-feature", 1)
    _write_doc(root, "beta-feature", 2)
    return root


def _reported_names(result: object) -> set[str]:
    """Return the file names a check result raised diagnostics against."""
    diagnostics = getattr(result, "diagnostics", [])
    return {d.path.name for d in diagnostics if d.path is not None}


class TestAnnotationsFeatureFilter:
    def test_an_unrestricted_pass_reports_every_feature(
        self, two_feature_vault: Path
    ) -> None:
        from ..checks.annotations import check_annotations

        names = _reported_names(check_annotations(two_feature_vault))

        assert any("alpha-feature" in n for n in names)
        assert any("beta-feature" in n for n in names)

    def test_a_named_feature_excludes_the_others(self, two_feature_vault: Path) -> None:
        from ..checks.annotations import check_annotations

        names = _reported_names(
            check_annotations(two_feature_vault, feature="alpha-feature")
        )

        assert names, "the filtered pass reported nothing at all"
        assert all("alpha-feature" in n for n in names), (
            f"the filter let another feature's documents through: {sorted(names)}"
        )

    def test_a_leading_hash_is_accepted(self, two_feature_vault: Path) -> None:
        from ..checks.annotations import check_annotations

        bare = _reported_names(
            check_annotations(two_feature_vault, feature="alpha-feature")
        )
        hashed = _reported_names(
            check_annotations(two_feature_vault, feature="#alpha-feature")
        )

        assert hashed == bare

    def test_an_unknown_feature_reports_nothing(self, two_feature_vault: Path) -> None:
        from ..checks.annotations import check_annotations

        assert not _reported_names(
            check_annotations(two_feature_vault, feature="no-such-feature")
        )


class TestMarkdownFeatureFilter:
    def test_an_unrestricted_pass_reports_every_feature(
        self, two_feature_vault: Path
    ) -> None:
        from ..checks.markdown import check_markdown

        names = _reported_names(check_markdown(two_feature_vault))

        assert any("alpha-feature" in n for n in names)
        assert any("beta-feature" in n for n in names)

    def test_a_named_feature_excludes_the_others(self, two_feature_vault: Path) -> None:
        from ..checks.markdown import check_markdown

        names = _reported_names(
            check_markdown(two_feature_vault, feature="alpha-feature")
        )

        assert names, "the filtered pass reported nothing at all"
        assert all("alpha-feature" in n for n in names), (
            f"the filter let another feature's documents through: {sorted(names)}"
        )

    def test_a_leading_hash_is_accepted(self, two_feature_vault: Path) -> None:
        from ..checks.markdown import check_markdown

        bare = _reported_names(
            check_markdown(two_feature_vault, feature="alpha-feature")
        )
        hashed = _reported_names(
            check_markdown(two_feature_vault, feature="#alpha-feature")
        )

        assert hashed == bare

    def test_an_unknown_feature_reports_nothing(self, two_feature_vault: Path) -> None:
        from ..checks.markdown import check_markdown

        assert not _reported_names(
            check_markdown(two_feature_vault, feature="no-such-feature")
        )
