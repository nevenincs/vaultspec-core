"""BM25 lexical ranking over record text."""

from __future__ import annotations

import math

import pytest

from vaultspec_core.search._lexical import BM25, STOPWORDS, tokenize, top_matches

pytestmark = [pytest.mark.unit]


class TestTokenize:
    def test_identifiers_split_into_lowercased_words(self) -> None:
        assert tokenize("Config-merge fsync_setting `Widget-2.14`") == [
            "config",
            "merge",
            "fsync",
            "setting",
            "widget",
            "2",
            "14",
        ]

    def test_stopwords_are_kept_by_the_tokenizer(self) -> None:
        assert tokenize("Why is the cache stale") == [
            "why",
            "is",
            "the",
            "cache",
            "stale",
        ]
        assert {"why", "is", "the"} <= STOPWORDS


class TestScores:
    def test_score_follows_the_okapi_formula(self) -> None:
        # Two documents, one query term present once in a two-term document.
        # idf = ln(1 + (N - n + 0.5) / (n + 0.5)) with N = 2 and n = 1.
        # The average length is 1.5, so the length norm is
        # k1 * (1 - b + b * 2 / 1.5) with k1 = 1.4 and b = 0.75.
        idf = math.log(1 + 1.5 / 1.5)
        norm = 1.4 * (1 - 0.75 + 0.75 * 2 / 1.5)
        expected = idf * 1 * (1.4 + 1) / (1 + norm)

        scores = BM25(["alpha beta", "gamma"]).scores("alpha")

        assert scores[0] == pytest.approx(expected)
        assert scores[1] == 0.0

    def test_rare_terms_outweigh_common_ones(self) -> None:
        corpus = [
            "cache cache rotation",
            "cache eviction",
            "cache warmup",
            "cache sizing",
        ]

        scores = BM25(corpus).scores("cache rotation")

        assert scores[0] == max(scores)
        assert all(score > 0 for score in scores)

    def test_repeated_terms_saturate(self) -> None:
        once, many, _ = BM25(["fsync", "fsync " * 10, "other"]).scores("fsync")

        assert many > once
        assert many < 3 * once

    def test_shorter_document_wins_at_equal_term_count(self) -> None:
        short, long = BM25(
            ["fsync setting", "fsync " + " ".join(f"word{i}" for i in range(40))]
        ).scores("fsync")

        assert short > long

    def test_stopword_only_query_scores_nothing(self) -> None:
        assert BM25(["the cache is why", "what was it"]).scores("why is the") == [
            0.0,
            0.0,
        ]

    def test_empty_corpus_texts_score_zero_without_failing(self) -> None:
        assert BM25(["", "  "]).scores("anything") == [0.0, 0.0]


class TestTopMatches:
    def test_returns_best_first_and_drops_non_matches(self) -> None:
        corpus = ["windows config merge defect", "unrelated text", "config merge"]

        assert top_matches("config merge defect windows", corpus, 5) == [0, 2]

    def test_respects_the_count(self) -> None:
        corpus = ["alpha one", "alpha two", "alpha three"]

        assert len(top_matches("alpha", corpus, 2)) == 2

    def test_ties_keep_corpus_order(self) -> None:
        assert top_matches("alpha", ["alpha x", "alpha y", "alpha z"], 3) == [0, 1, 2]

    @pytest.mark.parametrize("count", [0, -1])
    def test_non_positive_count_returns_nothing(self, count: int) -> None:
        assert top_matches("alpha", ["alpha"], count) == []

    def test_empty_corpus_returns_nothing(self) -> None:
        assert top_matches("alpha", [], 3) == []
