"""Tests for wiki-link extraction from document bodies and frontmatter.

Covers :func:`~vaultspec_core.vaultcore.links.extract_wiki_links` and
:func:`~vaultspec_core.vaultcore.links.extract_related_links` including
alias stripping, ``.md``-extension normalization, multiplicity preservation,
and malformed-link rejection.
"""

from collections import Counter

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
