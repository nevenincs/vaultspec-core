"""Metric (a): command and subcommand hotspots.

The hotspots metric answers the first question the MCP overhaul asks of the
corpus - which verb paths are actually exercised, and how often. It counts the
frequency of each ``(verb, subcommand)`` leaf across the normalized
:class:`~statistic.normalize.models.CallRecord` stream, where the leaf is the
record's full :attr:`~statistic.normalize.models.CallRecord.subcommand` verb
path (e.g. ``("vault", "check", "links")``).

:func:`compute_hotspots` is a pure function over an iterable of records: it
holds no I/O, reads no clock, and consumes only the records handed to it, so a
fixed record set always yields a byte-identical ranking. Ties break on the verb
path itself so the ordering is total and deterministic.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from statistic.normalize.models import CallRecord


@dataclass(frozen=True)
class VerbHotspot:
    """One verb path and the number of times it was invoked.

    Attributes:
        verb_path: The full verb path as a tuple of segments, e.g.
            ``("vault", "check", "all")``. An empty tuple marks a degenerate
            bare-executable invocation.
        count: The number of records that resolved to this verb path.
    """

    verb_path: tuple[str, ...]
    count: int


def compute_hotspots(records: Iterable[CallRecord]) -> tuple[VerbHotspot, ...]:
    """Rank verb paths by invocation frequency over the record stream.

    Args:
        records: The normalized call records to aggregate. Iterated once.

    Returns:
        The verb-path hotspots ordered by descending count, ties broken by the
        verb path ascending, so the ranking is total and deterministic.
    """
    counter: Counter[tuple[str, ...]] = Counter(record.subcommand for record in records)
    ranked = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    return tuple(VerbHotspot(verb_path, count) for verb_path, count in ranked)
