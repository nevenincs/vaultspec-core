"""The code-only stage: rank every candidate ADR without a network call.

Two signals, each cheap and each blind in a different place, fused by
reciprocal rank:

- **Fingerprint overlap.** The cosine of the source's and the candidate's
  artifact fingerprints, weighted by inverse document frequency so an artifact
  every ADR names (the vault itself, the CLI) says nothing. It finds decisions
  that govern the same module, verb or variable whatever their titles say.
- **Header overlap.** The cosine of the source's decision text against the
  candidate's header - feature, title and lead - over word tokens, again
  weighted by inverse document frequency. It finds decisions whose subject the
  source names in prose.

Artifacts named by more than :data:`~vaultspec_core.crossref._questions.
COMMON_ARTIFACT_SHARE` of the corpus are dropped from fingerprints as noise.
The stage is linear in the corpus and runs in milliseconds per source, so it
is the one stage that sees every candidate.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import TYPE_CHECKING, Final

from ._questions import COMMON_ARTIFACT_SHARE, OPTION_ARTIFACTS, RRF_K

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

    from ._corpus import AdrRecord

__all__ = ["Index", "fuse"]

#: A word token: a letter, then letters, digits, underscores or hyphens.
_TOKEN_RE: Final = re.compile(r"[a-z][a-z0-9_-]{2,}")

#: Words too common in decision prose to separate one ADR from another.
_STOPWORDS: Final = frozenset(
    [
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "are",
        "not",
        "from",
        "into",
        "its",
        "when",
        "only",
        "one",
        "each",
        "any",
        "but",
        "was",
        "has",
        "have",
        "which",
        "their",
        "than",
        "then",
        "all",
        "can",
        "will",
        "must",
    ]
)

type Vector = dict[str, float]


def _tokens(text: str) -> list[str]:
    return [
        token for token in _TOKEN_RE.findall(text.lower()) if token not in _STOPWORDS
    ]


def _weigh(counts: Mapping[str, int], df: Mapping[str, int], size: int) -> Vector:
    """Return the unit tf-idf vector of *counts* over terms *df* knows."""
    vector = {
        term: (1 + math.log(count)) * math.log(size / df[term])
        for term, count in counts.items()
        if df.get(term)
    }
    norm = math.sqrt(sum(value * value for value in vector.values())) or 1.0
    return {term: value / norm for term, value in vector.items()}


def _cosine(left: Vector, right: Vector) -> float:
    if len(left) > len(right):
        left, right = right, left
    return sum(value * right.get(term, 0.0) for term, value in left.items())


def fuse(rankings: Iterable[tuple[float, Sequence[str]]]) -> list[str]:
    """Fuse ranked stem lists by weighted reciprocal rank.

    Args:
        rankings: ``(weight, stems best first)`` pairs.

    Returns:
        Every stem any ranking holds, best first; ties break by stem.
    """
    scores: dict[str, float] = {}
    for weight, stems in rankings:
        for rank, stem in enumerate(stems, start=1):
            scores[stem] = scores.get(stem, 0.0) + weight / (RRF_K + rank)
    return sorted(scores, key=lambda stem: (-scores[stem], stem))


class Index:
    """The code-only signals over one corpus.

    Args:
        records: Every ADR of the corpus.
    """

    def __init__(self, records: Sequence[AdrRecord]) -> None:
        self.records = {record.stem: record for record in records}
        size = max(len(records), 1)
        ceiling = size * COMMON_ARTIFACT_SHARE
        artifact_df = Counter(name for r in records for name in r.artifacts)
        self._artifact_df = {n: c for n, c in artifact_df.items() if c < ceiling}
        self._fingerprints = {
            r.stem: _weigh(r.artifacts, self._artifact_df, size) for r in records
        }
        headers = {r.stem: Counter(_tokens(r.header())) for r in records}
        self._word_df = Counter(term for counts in headers.values() for term in counts)
        self._size = size
        self._headers = {
            stem: _weigh(counts, self._word_df, size)
            for stem, counts in headers.items()
        }

    def distinctive(self, stem: str, limit: int = OPTION_ARTIFACTS) -> list[str]:
        """The artifacts that best identify *stem* and that another ADR shares.

        Args:
            stem: The record.
            limit: The most artifacts returned.

        Returns:
            Up to *limit* artifact names, most distinctive first; an artifact
            no other ADR names cannot link two decisions, so it is left out.
        """
        weights = self._fingerprints.get(stem, {})
        shared = [name for name in weights if self._artifact_df.get(name, 0) >= 2]
        return sorted(shared, key=lambda name: (-weights[name], name))[:limit]

    def signals(self, source: AdrRecord) -> tuple[list[str], list[str]]:
        """Rank every other ADR for *source* by each code-only signal.

        Args:
            source: The ADR being cross-referenced; it need not belong to the
                corpus.

        Returns:
            Every other ADR's stem, best first, by fingerprint overlap and by
            header overlap.
        """
        others = [stem for stem in self.records if stem != source.stem]
        mine = self._fingerprints.get(source.stem) or _weigh(
            source.artifacts, self._artifact_df, self._size
        )
        text = _weigh(Counter(_tokens(source.decision)), self._word_df, self._size)
        by_artifact = sorted(
            others, key=lambda s: (-_cosine(mine, self._fingerprints[s]), s)
        )
        by_header = sorted(others, key=lambda s: (-_cosine(text, self._headers[s]), s))
        return by_artifact, by_header

    def rank(self, source: AdrRecord) -> list[str]:
        """Rank every other ADR for *source* by the fused code-only signals.

        Args:
            source: The ADR being cross-referenced.

        Returns:
            Every other ADR's stem, best first.
        """
        by_artifact, by_header = self.signals(source)
        return fuse(((1.0, by_artifact), (1.0, by_header)))
