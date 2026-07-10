"""Metric (g): token cost per command class.

This metric groups the attributed token cost of every record by its command
class - the leading verb - so the MCP overhaul can see which operations are the
expensive ones and would benefit most from a single MCP round-trip rather than a
shelled-out CLI call. Cost attribution is directional by construction and the
report must label it so: the Claude side is a per-assistant-message
approximation divided across a message's calls, while the Codex side is derived
from the deltas between cumulative token snapshots. The two are not exactly
comparable, so this metric also reports per-source totals for transparency.

The function is pure over the record stream. Only records that carry an
attributed :attr:`~statistic.normalize.models.CallRecord.token_cost` contribute
to a cost total, and the count of attributed versus total calls is reported so a
low total is never mistaken for a cheap verb when it is really an unattributed
one. Groupings are sorted by descending cost for a deterministic ordering.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from statistic.normalize.models import CallRecord


@dataclass(frozen=True)
class VerbCost:
    """The aggregated cost of one command class.

    Attributes:
        verb: The leading verb naming the command class.
        total_cost: The summed attributed token cost across the class's records.
        call_count: Every record in the class, attributed or not.
        attributed_calls: The records in the class that carried a token cost.
    """

    verb: str
    total_cost: int
    call_count: int
    attributed_calls: int


@dataclass(frozen=True)
class SourceCost:
    """The attributed token total for one corpus, kept separate.

    Attributes:
        source: The corpus, ``"claude"`` or ``"codex"``.
        total_cost: The summed attributed token cost of the corpus's records.
        attributed_calls: The corpus records that carried a token cost.
    """

    source: str
    total_cost: int
    attributed_calls: int


@dataclass(frozen=True)
class CostReport:
    """The per-command-class cost aggregate.

    Attributes:
        by_verb: The per-verb cost rows ranked by descending total cost.
        by_source: The per-corpus totals, a reminder that Claude and Codex cost
            attribution is directional and not exactly comparable.
        total_cost: The summed attributed token cost across every record.
    """

    by_verb: tuple[VerbCost, ...]
    by_source: tuple[SourceCost, ...]
    total_cost: int


def compute_cost(records: Iterable[CallRecord]) -> CostReport:
    """Group attributed token cost by command class and by source.

    Args:
        records: The normalized call records to aggregate. Iterated once.

    Returns:
        The :class:`CostReport` of per-verb and per-source cost totals, verbs
        ranked by descending cost.
    """
    verb_cost: dict[str, int] = {}
    verb_calls: dict[str, int] = {}
    verb_attributed: dict[str, int] = {}
    source_cost: dict[str, int] = {}
    source_attributed: dict[str, int] = {}
    total_cost = 0

    for record in records:
        verb_calls[record.verb] = verb_calls.get(record.verb, 0) + 1
        verb_cost.setdefault(record.verb, 0)
        verb_attributed.setdefault(record.verb, 0)
        if record.token_cost is None:
            continue
        verb_cost[record.verb] += record.token_cost
        verb_attributed[record.verb] += 1
        source = record.source
        source_cost[source] = source_cost.get(source, 0) + record.token_cost
        source_attributed[source] = source_attributed.get(source, 0) + 1
        total_cost += record.token_cost

    by_verb = tuple(
        VerbCost(verb, verb_cost[verb], verb_calls[verb], verb_attributed[verb])
        for verb in sorted(verb_calls, key=lambda name: (-verb_cost[name], name))
    )
    by_source = tuple(
        SourceCost(source, source_cost[source], source_attributed[source])
        for source in sorted(source_cost)
    )
    return CostReport(by_verb=by_verb, by_source=by_source, total_cost=total_cost)
