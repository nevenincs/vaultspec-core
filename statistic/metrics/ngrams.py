"""Metric (b): command-and-flag n-grams and flag co-occurrence.

Where the hotspots metric counts verb paths alone, this metric counts the full
*shape* of an invocation - the verb path together with the canonical set of flag
names it carried - so repeated patterns like ``vault add exec --feature --step``
surface as first-class candidates for a single MCP tool. It also reports which
flags tend to appear together, independent of the verb path, so the MCP surface
can bundle co-occurring options.

Both aggregates are pure functions of the record stream. Flag *names* only enter
the pattern and the co-occurrence set; flag *values* never do, so no feature tag,
step id, or path leaks into the n-gram keys. Ordering is total and deterministic:
patterns and pairs rank by descending count with ties broken on the key itself.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from itertools import combinations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from statistic.normalize.models import CallRecord


@dataclass(frozen=True)
class FlagPattern:
    """One ``(verb path, sorted flag names)`` shape and its frequency.

    Attributes:
        verb_path: The verb path the pattern was observed under.
        flags: The canonical flag names present on the record, sorted so the
            pattern key is order-independent. Empty when the invocation carried
            no flags.
        count: The number of records matching this exact shape.
    """

    verb_path: tuple[str, ...]
    flags: tuple[str, ...]
    count: int


@dataclass(frozen=True)
class FlagCooccurrence:
    """One unordered pair of flag names and how often they co-occurred.

    Attributes:
        pair: The two canonical flag names, sorted, that appeared together on
            the same invocation.
        count: The number of records on which both flags were present.
    """

    pair: tuple[str, str]
    count: int


@dataclass(frozen=True)
class NgramReport:
    """The command-and-flag n-gram aggregate.

    Attributes:
        patterns: The distinct ``(verb path, flag names)`` shapes ranked by
            descending frequency.
        cooccurrences: The flag-name pairs ranked by descending co-occurrence
            count.
    """

    patterns: tuple[FlagPattern, ...]
    cooccurrences: tuple[FlagCooccurrence, ...]


def compute_ngrams(records: Iterable[CallRecord]) -> NgramReport:
    """Aggregate command-and-flag patterns and flag co-occurrence.

    Args:
        records: The normalized call records to aggregate. Iterated once.

    Returns:
        The :class:`NgramReport` of ranked patterns and co-occurring flag pairs,
        both ordered deterministically by descending count then key.
    """
    pattern_counter: Counter[tuple[tuple[str, ...], tuple[str, ...]]] = Counter()
    pair_counter: Counter[tuple[str, str]] = Counter()
    for record in records:
        flag_names = tuple(sorted(record.flags))
        pattern_counter[record.subcommand, flag_names] += 1
        for pair in combinations(flag_names, 2):
            pair_counter[pair] += 1

    patterns = tuple(
        FlagPattern(verb_path, flags, count)
        for (verb_path, flags), count in sorted(
            pattern_counter.items(), key=lambda item: (-item[1], item[0])
        )
    )
    cooccurrences = tuple(
        FlagCooccurrence(pair, count)
        for pair, count in sorted(
            pair_counter.items(), key=lambda item: (-item[1], item[0])
        )
    )
    return NgramReport(patterns=patterns, cooccurrences=cooccurrences)
