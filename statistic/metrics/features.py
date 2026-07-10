"""Metric (c): features utilized against the declared capability inventory.

This metric reduces the record stream to the *set* of distinct verb paths that
were exercised at all, then partitions that set against the declared-capability
denominator parsed from the CLI reference. A verb path present in both the
observed set and the inventory is *utilized*; a verb path observed but absent
from the inventory is *undeclared* - a candidate miss or a reference that lags
the installed binary, never silently dropped.

The function is pure over the record stream and the inventory. It reports only
verb paths, never counts or command bodies, so its output is the exercised
surface itself. Both partitions are sorted for a deterministic, total ordering.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from statistic.metrics.capability import CapabilityInventory
    from statistic.normalize.models import CallRecord


@dataclass(frozen=True)
class FeaturesUtilized:
    """The exercised verb-path surface, partitioned by declaration.

    Attributes:
        utilized: The distinct verb paths that were both observed and declared
            by the inventory, sorted.
        undeclared: The distinct verb paths that were observed but not declared,
            sorted. These are candidate misses, surfaced rather than dropped.
    """

    utilized: tuple[tuple[str, ...], ...]
    undeclared: tuple[tuple[str, ...], ...]


def compute_features_utilized(
    records: Iterable[CallRecord],
    inventory: CapabilityInventory,
) -> FeaturesUtilized:
    """Partition the observed verb-path set against the declared inventory.

    Args:
        records: The normalized call records to reduce to a verb-path set.
            Iterated once.
        inventory: The declared-capability denominator to intersect against.

    Returns:
        The :class:`FeaturesUtilized` split of declared-and-used verb paths from
        observed-but-undeclared ones, both sorted deterministically.
    """
    observed = {record.subcommand for record in records}
    utilized = sorted(path for path in observed if inventory.declares_verb_path(path))
    undeclared = sorted(
        path for path in observed if not inventory.declares_verb_path(path)
    )
    return FeaturesUtilized(utilized=tuple(utilized), undeclared=tuple(undeclared))
