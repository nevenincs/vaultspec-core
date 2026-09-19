"""Tests for wiki-link extraction from document bodies and frontmatter.

Covers :func:`~vaultspec_core.vaultcore.links.extract_wiki_links` and
:func:`~vaultspec_core.vaultcore.links.extract_related_links` including
alias stripping, ``.md``-extension normalization, multiplicity preservation,
and malformed-link rejection.
"""

from collections import Counter
from typing import ClassVar

import pytest

from .. import extract_related_links, extract_wiki_links

pytestmark = [pytest.mark.unit]


class TestExtractWikiLinks:
    def test_single_link(self):
        assert extract_wiki_links("See [[MyDoc]] for details") == Counter({"MyDoc": 1})

    def test_multiple_links(self):
        text = "See [[DocA]] and [[DocB]] here"
        assert extract_wiki_links(text) == Counter({"DocA": 1, "DocB": 1})

    def test_aliased_link(self):
        assert extract_wiki_links("See [[DocA|Display Name]]") == Counter({"DocA": 1})

    def test_no_links(self):
        assert extract_wiki_links("No links here") == Counter()

    def test_empty_string(self):
        assert extract_wiki_links("") == Counter()

    def test_link_with_spaces(self):
        assert extract_wiki_links("[[My Document]]") == Counter({"My Document": 1})

    def test_duplicate_links_preserve_multiplicity(self):
        text = "[[DocA]] and [[DocA]] again"
        result = extract_wiki_links(text)
        assert result == Counter({"DocA": 2})
        assert result["DocA"] == 2

    def test_triple_citation_yields_count_three(self):
        text = "[[x]] then [[x]] then [[x]]"
        assert extract_wiki_links(text) == Counter({"x": 3})

    def test_mixed_multiplicity(self):
        text = "[[a]] [[b]] [[a]] [[c]] [[a]] [[b]]"
        assert extract_wiki_links(text) == Counter({"a": 3, "b": 2, "c": 1})

    def test_aliased_duplicates_collapse_to_target_count(self):
        text = "[[DocA|One]] and [[DocA|Two]]"
        assert extract_wiki_links(text) == Counter({"DocA": 2})

    def test_returns_counter_instance(self):
        assert isinstance(extract_wiki_links("[[x]]"), Counter)

    def test_membership_and_iteration_behave_like_keys(self):
        result = extract_wiki_links("[[a]] [[a]] [[b]]")
        assert "a" in result
        assert "b" in result
        assert "missing" not in result
        assert set(result) == {"a", "b"}


class TestExtractRelatedLinks:
    def test_valid_wikilinks(self):
        related = ["[[DocA]]", "[[DocB]]"]
        assert extract_related_links(related) == Counter({"DocA": 1, "DocB": 1})

    def test_aliased_wikilinks(self):
        related = ["[[DocA|Alias]]"]
        assert extract_related_links(related) == Counter({"DocA": 1})

    def test_malformed_links(self):
        related = ["not-a-link", "DocB"]
        result = extract_related_links(related)
        assert result == Counter()

    def test_empty_list(self):
        assert extract_related_links([]) == Counter()

    def test_mixed_valid_and_malformed(self):
        related = ["[[Valid]]", "invalid", "[[Also Valid]]"]
        result = extract_related_links(related)
        assert result == Counter({"Valid": 1, "Also Valid": 1})

    def test_duplicate_related_entries_preserve_multiplicity(self):
        related = ["[[DocA]]", "[[DocA]]"]
        result = extract_related_links(related)
        assert result == Counter({"DocA": 2})
        assert result["DocA"] == 2

    def test_returns_counter_instance(self):
        assert isinstance(extract_related_links(["[[x]]"]), Counter)


class TestScanGuardsStayCoupledToTheirPatterns:
    """The cheap substring guards must not be able to skip a real finding.

    Three checkers skip a document whose body cannot contain what they look
    for - ``"["`` for link scans, ``"{"`` for placeholder scans - because
    stripping only ever removes text, so a body without the character has
    nothing to report whatever the strip would have produced. On a
    4,738-document production vault this skips 82% and 92% of documents
    respectively and cuts ``vault check all`` from 7.2 s to 5.5 s.

    The hazard is coupling: widen one of these patterns to match something
    that does not require its guard character and the guard starts silently
    hiding findings. These tests fail if that ever happens.
    """

    #: Bodies with no bracket and no brace, including shapes that look
    #: link-like or placeholder-like without the delimiter.
    _UNGUARDED_BODIES: ClassVar[list[str]] = [
        "plain prose with no delimiters at all\n",
        "a link-ish thing: see https://example.com/page\n",
        "parens (like these) and pipes | and dashes - and backticks `x`\n",
        "wiki style without brackets: page-name|Display\n",
        "placeholder-ish: feature, date, plan_name\n",
        "```\nfenced code with no delimiters\n```\n",
        "",
    ]

    def test_the_markdown_link_pattern_requires_an_opening_bracket(self) -> None:
        from ..checks.body_links import _MD_LINK_RE

        for body in self._UNGUARDED_BODIES:
            assert _MD_LINK_RE.search(body) is None, (
                f"the markdown-link pattern matched a body with no '[': {body!r}. "
                "check_body_links skips such bodies, so this finding would be lost."
            )

    def test_the_wiki_link_pattern_requires_an_opening_bracket(self) -> None:
        from ..links import _WIKI_LINK_RE

        for body in self._UNGUARDED_BODIES:
            assert _WIKI_LINK_RE.search(body) is None, (
                f"the wiki-link pattern matched a body with no '[': {body!r}. "
                "extract_wiki_links returns early on such bodies."
            )

    def test_the_placeholder_pattern_requires_an_opening_brace(self) -> None:
        from ..checks.placeholders import _PLACEHOLDER_RE

        for body in self._UNGUARDED_BODIES:
            assert _PLACEHOLDER_RE.search(body) is None, (
                f"the placeholder pattern matched a body with no '{{': {body!r}. "
                "check_placeholders skips such bodies, so this finding would be lost."
            )

    def test_extract_wiki_links_agrees_with_the_unguarded_scan(self) -> None:
        """The early return must equal what the full strip-and-scan produced."""
        from ..links import extract_wiki_links, strip_non_prose, wiki_links_from_prose

        bodies = [
            *self._UNGUARDED_BODIES,
            "prose with [[a-target]] in it\n",
            "[[one]] and [[two|Display]] and [[one]] again\n",
            "fenced:\n```\n[[not-a-link]]\n```\n",
            "inline `[[not-a-link]]` span\n",
            "<!-- [[commented-out]] -->\n",
            "mixed [[real]] and `[[fake]]`\n",
        ]
        for body in bodies:
            assert extract_wiki_links(body) == wiki_links_from_prose(
                strip_non_prose(body)
            ), f"early return disagreed with the full scan for {body!r}"
