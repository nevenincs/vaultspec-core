"""Metric (f): overuse versus declared capability and dead surface.

This metric places observed usage side by side with the declared-capability
denominator to answer two questions the MCP overhaul needs: which verbs are
invoked disproportionately (overuse, the candidates for a first-class MCP tool),
and which declared verbs are never invoked at all (dead surface, the candidates
to omit). The dead surface is exactly the inventory's verb-path set minus the
observed set, so it is a closed, verifiable difference rather than an estimate.

The function is pure over the record stream and the inventory. It reports verb
paths and counts only. Observed counts, dead surface, and undeclared usage are
each sorted for a deterministic, total ordering.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

from statistic.metrics.hotspots import VerbHotspot

if TYPE_CHECKING:
    from collections.abc import Iterable

    from statistic.metrics.capability import CapabilityInventory
    from statistic.normalize.models import CallRecord


@dataclass(frozen=True)
class SurfaceReport:
    """The observed-versus-declared surface comparison.

    Attributes:
        observed_declared: Declared verb paths that were invoked, with their
            counts, ranked by descending count. This is the overuse view: the
            top entries are the disproportionately-hit verbs.
        undeclared_usage: Observed verb paths absent from the inventory, with
            counts, ranked. Candidate misses or a lagging reference.
        dead_surface: Declared verb paths never invoked, sorted. The inventory
            minus the observed set.
        declared_total: The size of the declared verb-path denominator.
        observed_declared_count: How many declared verb paths were invoked at
            least once.
    """

    observed_declared: tuple[VerbHotspot, ...]
    undeclared_usage: tuple[VerbHotspot, ...]
    dead_surface: tuple[tuple[str, ...], ...]
    declared_total: int
    observed_declared_count: int

    @property
    def coverage(self) -> float:
        """Return the fraction of the declared surface that was invoked.

        Returns:
            ``observed_declared_count / declared_total``, or ``0.0`` when the
            inventory is empty.
        """
        if self.declared_total == 0:
            return 0.0
        return self.observed_declared_count / self.declared_total


def compute_surface(
    records: Iterable[CallRecord],
    inventory: CapabilityInventory,
) -> SurfaceReport:
    """Compare observed verb-path usage against the declared denominator.

    Args:
        records: The normalized call records to aggregate. Iterated once.
        inventory: The declared-capability denominator to measure against.

    Returns:
        The :class:`SurfaceReport` of overuse, undeclared usage, and dead
        surface, each ordered deterministically.
    """
    counter: Counter[tuple[str, ...]] = Counter(record.subcommand for record in records)

    observed_declared = tuple(
        VerbHotspot(verb_path, count)
        for verb_path, count in sorted(
            (
                (path, count)
                for path, count in counter.items()
                if inventory.declares_verb_path(path)
            ),
            key=lambda item: (-item[1], item[0]),
        )
    )
    undeclared_usage = tuple(
        VerbHotspot(verb_path, count)
        for verb_path, count in sorted(
            (
                (path, count)
                for path, count in counter.items()
                if not inventory.declares_verb_path(path)
            ),
            key=lambda item: (-item[1], item[0]),
        )
    )
    observed_paths = set(counter)
    dead_surface = tuple(sorted(inventory.verb_paths - observed_paths))
    return SurfaceReport(
        observed_declared=observed_declared,
        undeclared_usage=undeclared_usage,
        dead_surface=dead_surface,
        declared_total=len(inventory.verb_paths),
        observed_declared_count=len(observed_paths & inventory.verb_paths),
    )
