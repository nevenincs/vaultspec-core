"""Okapi BM25 over record text: the in-process lexical ranking hosted search adds.

The summary pass of hosted search ranks records by their summary cards, and a
card cannot carry every body detail: a setting named once in a long record, or
a defect described in one paragraph, is invisible to it. Word overlap with the
query sees the whole body, so a few of its leading records join the shortlist
that is read in full. On the evaluation queries this union recovered answers
the summary pass missed. On its own it ranks well below the hosted judgments,
so it never orders the results, only widens what is read.

This is the one lexical ranker in the package. It needs no index: the corpus
is scored per query from the text already in memory, which keeps it exact
against the vault on disk.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["BM25", "STOPWORDS", "tokenize", "top_matches"]

#: A token: a run of ASCII letters and digits in lowercased text. Hyphenated
#: and snake-case identifiers split into their words, so ``config-merge`` in a
#: record matches "config merge" in a question.
_TOKEN: Final = re.compile(r"[a-z0-9]+")

#: Function words dropped from both sides. They occur in nearly every record,
#: so they carry no evidence and only dilute the length normalisation.
STOPWORDS: Final = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "can",
        "did",
        "do",
        "does",
        "for",
        "from",
        "how",
        "in",
        "is",
        "it",
        "no",
        "not",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
        "was",
        "were",
        "what",
        "which",
        "why",
        "with",
    }
)

#: Term-frequency saturation. Past a few occurrences a repeated word adds
#: little, which keeps a long ledger that repeats a path from outranking a
#: short record that states the answer once.
_K1: Final = 1.4

#: Strength of the document-length normalisation.
_B: Final = 0.75


def tokenize(text: str) -> list[str]:
    """Split *text* into lowercased alphanumeric tokens.

    Args:
        text: Any text.

    Returns:
        The tokens in order, stopwords included.
    """
    return _TOKEN.findall(text.lower())


def _term_counts(text: str) -> Counter[str]:
    """Count the non-stopword tokens of *text*."""
    counts = Counter(tokenize(text))
    # Dropping the few stopwords from the tally is far cheaper than testing
    # every token of a long record against the set.
    for word in STOPWORDS.intersection(counts):
        del counts[word]
    return counts


class BM25:
    """Score a fixed set of texts against queries with Okapi BM25.

    Args:
        texts: The corpus, one text per document; scores come back in this
            order.
    """

    def __init__(self, texts: Sequence[str]) -> None:
        self._counts = [_term_counts(text) for text in texts]
        self._lengths = [sum(counts.values()) for counts in self._counts]
        total = sum(self._lengths)
        # An all-empty corpus has no average; any positive value leaves every
        # score at zero, because no term can match.
        self._average = total / len(self._lengths) if total else 1.0
        size = len(self._counts)
        frequency = Counter(term for counts in self._counts for term in counts)
        self._idf = {
            term: math.log(1 + (size - count + 0.5) / (count + 0.5))
            for term, count in frequency.items()
        }

    def scores(self, query: str) -> list[float]:
        """Score every document against *query*.

        Args:
            query: The query text.

        Returns:
            One non-negative score per document, in corpus order; zero for a
            document that shares no term with the query.
        """
        terms = [
            term
            for term in tokenize(query)
            if term not in STOPWORDS and term in self._idf
        ]
        results: list[float] = []
        for counts, length in zip(self._counts, self._lengths, strict=True):
            norm = _K1 * (1 - _B + _B * length / self._average)
            score = 0.0
            for term in terms:
                frequency = counts.get(term, 0)
                if frequency:
                    score += (
                        self._idf[term] * frequency * (_K1 + 1) / (frequency + norm)
                    )
            results.append(score)
        return results


def top_matches(query: str, texts: Sequence[str], count: int) -> list[int]:
    """Return the indices of the *count* texts that best match *query*.

    Args:
        query: The query text.
        texts: The corpus.
        count: How many indices to return at most.

    Returns:
        Indices into *texts*, best first, ties in corpus order. A text with
        no term in common with the query is never returned.
    """
    if count < 1 or not texts:
        return []
    scores = BM25(texts).scores(query)
    ranked = sorted(
        (index for index, score in enumerate(scores) if score > 0),
        key=lambda index: (-scores[index], index),
    )
    return ranked[:count]
