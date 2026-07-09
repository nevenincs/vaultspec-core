"""Metric (e): tool-call misses, undeclared flags, and retry corrections.

This is the correctness-critical metric of the seven, because the whole module
exists partly to separate genuine invocation *misses* from by-design non-zero
exits. It reads three distinct miss signals off the normalized record stream:

* **errors** - records whose
  :attr:`~statistic.normalize.models.CallRecord.exit_status` is
  :attr:`~statistic.normalize.exit_status.ExitStatus.ERROR`. A *findings* status
  is never counted, so a ``vault check`` that reported drift and the Claude
  ``distutils-precedence.pth`` venv noise both stay out of the miss rate by
  construction - the adapters already resolved them upstream.
* **undeclared flags** - flags observed on a *declared* verb path that the
  capability inventory does not declare for it. This is advisory (the reference
  may lag the binary), so it is reported as a candidate, never a hard miss.
* **retry corrections** - within one session, ordered by activity timestamp, an
  errored call immediately followed by a materially different flag set on the
  same verb. This is the highest-value and most fragile signal: it captures the
  operator correcting a failed invocation, which points straight at an ergonomic
  gap the MCP surface should eliminate.

Every aggregate is a pure function of the inputs, with total, deterministic
ordering.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import pairwise
from typing import TYPE_CHECKING

from statistic.normalize.exit_status import ExitStatus

if TYPE_CHECKING:
    from collections.abc import Iterable

    from statistic.metrics.capability import CapabilityInventory
    from statistic.normalize.models import CallRecord


@dataclass(frozen=True)
class VerbErrorCount:
    """One verb path and its genuine-error count.

    Attributes:
        verb_path: The verb path the errors occurred under.
        count: The number of records under it with an ``ERROR`` exit status.
    """

    verb_path: tuple[str, ...]
    count: int


@dataclass(frozen=True)
class UndeclaredFlagCandidate:
    """One flag observed on a declared verb path but not declared for it.

    Attributes:
        verb_path: The declared verb path the flag was observed under.
        flag: The canonical flag name absent from the inventory's declared set.
        count: The number of records carrying this undeclared flag on the verb.
    """

    verb_path: tuple[str, ...]
    flag: str
    count: int


@dataclass(frozen=True)
class RetryCorrection:
    """One errored call corrected by a differently-flagged retry.

    Attributes:
        session_id: The session both calls belong to.
        verb: The shared leading verb of the errored call and its retry.
        before_flags: The sorted flag names of the errored call.
        after_flags: The sorted flag names of the correcting retry.
    """

    session_id: str
    verb: str
    before_flags: tuple[str, ...]
    after_flags: tuple[str, ...]


@dataclass(frozen=True)
class MissReport:
    """The combined tool-call-miss aggregate.

    Attributes:
        total_records: Every record considered, the miss-rate denominator.
        error_records: The count of genuine ``ERROR`` records.
        errors_by_verb: The genuine errors grouped by verb path, ranked by
            descending count.
        undeclared_flags: The advisory undeclared-flag candidates, ranked by
            descending count.
        retry_corrections: The detected errored-call-then-retry corrections, in
            session and sequence order.
    """

    total_records: int
    error_records: int
    errors_by_verb: tuple[VerbErrorCount, ...]
    undeclared_flags: tuple[UndeclaredFlagCandidate, ...]
    retry_corrections: tuple[RetryCorrection, ...]

    @property
    def miss_rate(self) -> float:
        """Return the genuine-error fraction of all records.

        Returns:
            ``error_records / total_records``, or ``0.0`` when there are no
            records.
        """
        if self.total_records == 0:
            return 0.0
        return self.error_records / self.total_records


def _errors_by_verb(records: list[CallRecord]) -> tuple[VerbErrorCount, ...]:
    """Count genuine ``ERROR`` records per verb path, ranked."""
    counter: Counter[tuple[str, ...]] = Counter(
        record.subcommand
        for record in records
        if record.exit_status is ExitStatus.ERROR
    )
    return tuple(
        VerbErrorCount(verb_path, count)
        for verb_path, count in sorted(
            counter.items(), key=lambda item: (-item[1], item[0])
        )
    )


def _undeclared_flags(
    records: list[CallRecord],
    inventory: CapabilityInventory,
) -> tuple[UndeclaredFlagCandidate, ...]:
    """Count flags on declared verb paths that the inventory omits, ranked."""
    counter: Counter[tuple[tuple[str, ...], str]] = Counter()
    for record in records:
        if not inventory.declares_verb_path(record.subcommand):
            continue
        for flag in record.flags:
            if not inventory.declares_flag(record.subcommand, flag):
                counter[record.subcommand, flag] += 1
    return tuple(
        UndeclaredFlagCandidate(verb_path, flag, count)
        for (verb_path, flag), count in sorted(
            counter.items(), key=lambda item: (-item[1], item[0])
        )
    )


def _retry_corrections(records: list[CallRecord]) -> tuple[RetryCorrection, ...]:
    """Detect errored calls corrected by a differently-flagged same-verb retry.

    Records are grouped by session and ordered by activity timestamp; an
    adjacent pair whose first element errored, whose verbs match, and whose flag
    name sets differ is a correction.

    The sequence is intentionally keyed off ``session_id`` plus ``timestamp``,
    not off :attr:`~statistic.normalize.models.CallRecord.retry_key`. That field
    is a per-call linkage anchor - on the Codex side the per-call-unique
    ``call_id`` - so literal ordering by it is meaningless; wall-clock order
    within a session is the correct and portable sequencing signal across both
    corpora. ``retry_key`` is retained for record linkage, not for this ordering.
    """
    by_session: defaultdict[str, list[CallRecord]] = defaultdict(list)
    for record in records:
        by_session[record.session_id].append(record)

    corrections: list[RetryCorrection] = []
    for session_id in sorted(by_session):
        ordered = sorted(by_session[session_id], key=lambda record: record.timestamp)
        for previous, current in pairwise(ordered):
            if previous.exit_status is not ExitStatus.ERROR:
                continue
            if previous.verb != current.verb:
                continue
            before = tuple(sorted(previous.flags))
            after = tuple(sorted(current.flags))
            if before != after:
                corrections.append(
                    RetryCorrection(session_id, previous.verb, before, after)
                )
    return tuple(corrections)


def compute_misses(
    records: Iterable[CallRecord],
    inventory: CapabilityInventory,
) -> MissReport:
    """Aggregate genuine errors, undeclared flags, and retry corrections.

    Args:
        records: The normalized call records to analyze. Materialized once so
            the three passes share one snapshot.
        inventory: The declared-capability denominator for advisory flag checks.

    Returns:
        The :class:`MissReport` combining all three miss signals.
    """
    snapshot = list(records)
    error_records = sum(
        1 for record in snapshot if record.exit_status is ExitStatus.ERROR
    )
    return MissReport(
        total_records=len(snapshot),
        error_records=error_records,
        errors_by_verb=_errors_by_verb(snapshot),
        undeclared_flags=_undeclared_flags(snapshot, inventory),
        retry_corrections=_retry_corrections(snapshot),
    )
