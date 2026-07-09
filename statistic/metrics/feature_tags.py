"""Metric (d): ``--feature`` tag usage distribution.

The normalizer already folds the short ``-f`` form into the canonical
``--feature`` flag and records its argument as
:attr:`~statistic.normalize.models.CallRecord.feature_tag`, so this metric reads
that single field. It reports the distribution of tag values across the record
stream, plus how many invocations carried a feature tag at all versus how many
did not, which tells the MCP overhaul how central feature scoping is to real
usage.

The function is pure over the record stream. Tag *values* are legitimate report
content - they are project feature slugs, not command bodies or personal paths -
so they are surfaced directly. The distribution is ranked by descending count
with ties broken on the tag value for a deterministic ordering.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from statistic.normalize.models import CallRecord


@dataclass(frozen=True)
class FeatureTagCount:
    """One feature-tag value and how often it was supplied.

    Attributes:
        tag: The canonical ``--feature`` argument value.
        count: The number of records that carried this tag.
    """

    tag: str
    count: int


@dataclass(frozen=True)
class FeatureTagUsage:
    """The feature-tag usage distribution.

    Attributes:
        counts: The per-tag counts ranked by descending frequency, ties broken
            on the tag value.
        tagged: The number of records that carried any feature tag.
        untagged: The number of records that carried none.
    """

    counts: tuple[FeatureTagCount, ...]
    tagged: int
    untagged: int


def compute_feature_tag_usage(records: Iterable[CallRecord]) -> FeatureTagUsage:
    """Aggregate the distribution of ``--feature`` tag values.

    Args:
        records: The normalized call records to aggregate. Iterated once.

    Returns:
        The :class:`FeatureTagUsage` distribution and the tagged/untagged split.
    """
    counter: Counter[str] = Counter()
    untagged = 0
    for record in records:
        if record.feature_tag is None:
            untagged += 1
        else:
            counter[record.feature_tag] += 1
    counts = tuple(
        FeatureTagCount(tag, count)
        for tag, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    )
    return FeatureTagUsage(
        counts=counts, tagged=sum(counter.values()), untagged=untagged
    )
