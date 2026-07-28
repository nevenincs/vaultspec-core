"""Vault-wide orientation rollup (decisions D2 / D4 / D6).

Sibling of :mod:`vaultspec_core.vaultcore.orientation_models` (the
dataclasses and recency helpers this module builds on) and
:mod:`vaultspec_core.vaultcore.orientation_trace` (the targeted
grounding-trace view). :func:`compute_rollup` is the only entry point:
it returns the vault-wide :class:`~vaultspec_core.vaultcore.orientation_models.Rollup`
with active features, plans in flight, recently completed plans, recent
documents grouped by type, and per-feature execution-record activity.

The public surface re-exports every name from
:mod:`vaultspec_core.vaultcore.orientation`; import from there, not this
module, at call sites outside the package.
"""

from __future__ import annotations

import datetime as _dt
from typing import TYPE_CHECKING

from .models import DocType
from .orientation_models import (
    _NO_DATE,
    ActiveFeature,
    ExecActivity,
    PlanInFlight,
    RecentDocument,
    Rollup,
    recency_date,
    recency_string,
)

if TYPE_CHECKING:
    from pathlib import Path

    from ..graph.api import DocNode, VaultGraph
    from ..plan.status import PlanStatus, PlanStatusEntry

__all__ = ["compute_rollup"]


def compute_rollup(
    root_dir: Path,
    *,
    limit: int = 10,
    since_days: int | None = None,
    verbose_exec: bool = False,
    graph: VaultGraph | None = None,
    today: _dt.date | None = None,
) -> Rollup:
    """Compute the vault-wide orientation rollup.

    Args:
        root_dir: Project root directory.
        limit: Maximum number of recent documents to return per document
            type. The cap is applied per group, not across a flat list, so
            one high-volume type cannot crowd the others out.
        since_days: When set, switch to a day-window query: only documents
            whose recency is within this many days of *today* are
            considered, still capped per group by *limit*.
        verbose_exec: When ``True``, list execution records per record in
            ``recent_documents`` (capped by *limit*) and leave
            ``exec_activity`` empty. When ``False`` (default), execution
            records are summarised per feature in ``exec_activity`` and
            excluded from ``recent_documents`` so they never flood the view.
        graph: Optional pre-built :class:`~vaultspec_core.graph.VaultGraph`
            to reuse; one is built from *root_dir* when omitted.
        today: Reference date for the *since_days* window, defaulting to
            :meth:`datetime.date.today`. Exposed for deterministic tests.

    Returns:
        A fully populated :class:`Rollup`.
    """
    from ..graph.api import VaultGraph
    from ..plan.status import collect_all_statuses
    from .query import get_stats

    g = graph if graph is not None else VaultGraph(root_dir)
    reference = today if today is not None else _dt.date.today()

    # Index documents are derived aggregates of a feature's other docs;
    # including them in feature counts or the recent set double-counts and
    # relists the same documents. Exclude them from every
    # summary view here while leaving the graph itself untouched.
    real_nodes = [
        n for n in g.nodes.values() if not n.phantom and n.doc_type is not DocType.INDEX
    ]

    # Parse every plan once (predecessor D6) and share the result across
    # the in-flight bucket, the recently-completed bucket, and the
    # per-feature plan tail, rather than scanning plans three times.
    entries = collect_all_statuses(root_dir, graph=g)
    status_by_feature: dict[str, PlanStatus] = {}
    for entry in entries:
        feature = entry.document.feature
        if entry.status is not None and feature and feature not in status_by_feature:
            status_by_feature[feature] = entry.status

    active_features = _active_features(real_nodes, status_by_feature)
    plans_in_flight, recently_completed = _plan_buckets(entries, g)
    recent_documents = _recent_documents(
        real_nodes,
        limit=limit,
        since_days=since_days,
        reference=reference,
        include_exec=verbose_exec,
    )
    exec_activity = (
        []
        if verbose_exec
        else _exec_activity(
            real_nodes, limit=limit, since_days=since_days, reference=reference
        )
    )
    totals = get_stats(root_dir, graph=g)

    return Rollup(
        active_features=active_features,
        plans_in_flight=plans_in_flight,
        recently_completed=recently_completed,
        recent_documents=recent_documents,
        exec_activity=exec_activity,
        totals=totals,
        limit=limit,
        since_days=since_days,
    )


def _active_features(
    nodes: list[DocNode],
    status_by_feature: dict[str, PlanStatus] | None = None,
) -> list[ActiveFeature]:
    """Build the active-feature list ordered by latest activity descending.

    A feature is active when at least one of its non-archived documents
    carries the tag; archived documents are already excluded from the
    graph scan, so every feature seen here is active.
    """
    status_by_feature = status_by_feature or {}
    by_feature: dict[str, list[DocNode]] = {}
    for node in nodes:
        if node.feature:
            by_feature.setdefault(node.feature, []).append(node)

    features: list[tuple[_dt.date, ActiveFeature]] = []
    for name, feat_nodes in by_feature.items():
        latest = max(recency_date(n) for n in feat_nodes)
        latest_str = latest.isoformat() if latest is not _NO_DATE else None
        status = status_by_feature.get(name)
        features.append(
            (
                latest,
                ActiveFeature(
                    name=name,
                    doc_count=len(feat_nodes),
                    latest_activity=latest_str,
                    has_plan=any(n.doc_type is DocType.PLAN for n in feat_nodes),
                    plan_tier=status.tier.value if status is not None else None,
                    plan_steps_completed=(
                        status.steps_completed if status is not None else 0
                    ),
                    plan_step_count=status.step_count if status is not None else 0,
                    plan_completion_percent=(
                        status.completion_percent if status is not None else 0.0
                    ),
                ),
            )
        )

    # Most recently active first; ties broken by feature name for a stable,
    # platform-independent order.
    features.sort(key=lambda item: (item[0], item[1].name), reverse=True)
    return [feature for _, feature in features]


#: Maximum recently-completed plans shown in the rollup. The bucket is a
#: courtesy so a just-finished plan does not vanish; it is
#: not the full archive, so it stays small.
_RECENTLY_COMPLETED_CAP = 5


def _plan_buckets(
    entries: list[PlanStatusEntry],
    graph: VaultGraph,
) -> tuple[list[PlanInFlight], list[PlanInFlight]]:
    """Split parsed plan statuses into in-flight and recently-completed.

    Consumes the shared batched statuses (predecessor D6): a plan is in
    flight when it has at least one open step (decision D2) and recently
    completed when it has steps and none are open. Both
    buckets are ordered most recently modified first; the completed bucket
    is capped at :data:`_RECENTLY_COMPLETED_CAP`. Unparseable plans are
    skipped here - they surface in the targeted trace and the deep
    single-plan validator, not the rollup.
    """
    in_flight: list[tuple[_dt.date, str, PlanInFlight]] = []
    completed: list[tuple[_dt.date, str, PlanInFlight]] = []
    for entry in entries:
        status = entry.status
        if status is None or status.step_count <= 0:
            continue
        node = graph.nodes.get(entry.document.name)
        recency = recency_date(node) if node is not None else _NO_DATE
        recency_str = recency.isoformat() if recency is not _NO_DATE else None
        plan = _plan_in_flight(entry, status, recency_str)
        bucket = in_flight if plan.open_steps > 0 else completed
        bucket.append((recency, entry.document.name, plan))

    in_flight.sort(key=lambda item: (item[0], item[1]), reverse=True)
    completed.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return (
        [plan for _, _, plan in in_flight],
        [plan for _, _, plan in completed[:_RECENTLY_COMPLETED_CAP]],
    )


def _plan_in_flight(
    entry: PlanStatusEntry,
    status: PlanStatus,
    recency_str: str | None,
) -> PlanInFlight:
    """Pre-shape one plan's status into a :class:`PlanInFlight` row."""
    return PlanInFlight(
        stem=entry.document.name,
        feature=entry.document.feature,
        tier=status.tier.value,
        open_steps=status.step_count - status.steps_completed,
        closed_steps=status.steps_completed,
        total_steps=status.step_count,
        completion_percent=status.completion_percent,
        wave_count=status.wave_count,
        waves_completed=status.waves_completed,
        phase_count=status.phase_count,
        phases_completed=status.phases_completed,
        next_open_step=status.next_open_step,
        exec_missing=len(status.exec_missing_ids),
        modified=recency_str,
    )


def _recent_documents(
    nodes: list[DocNode],
    *,
    limit: int,
    since_days: int | None,
    reference: _dt.date,
    include_exec: bool,
) -> dict[str, list[RecentDocument]]:
    """Build the recent-documents view grouped by type.

    The recency order (most recent first) is established once. The
    *limit* is then applied **per document-type group** rather than across
    a flat list, so a high-volume type (execution records) cannot crowd
    every other type out of the view. A *since_days* window filters to
    documents within the window first; the per-group cap still applies.
    Execution records are excluded unless *include_exec* is set (they are
    otherwise summarised by :func:`_exec_activity`).
    """
    dated = sorted(
        ((node, recency_date(node)) for node in nodes),
        key=lambda item: (item[1], item[0].name),
        reverse=True,
    )

    cutoff = (
        reference - _dt.timedelta(days=since_days) if since_days is not None else None
    )

    grouped: dict[str, list[RecentDocument]] = {}
    for node, recency in dated:
        if cutoff is not None and (recency is _NO_DATE or recency < cutoff):
            continue
        if node.doc_type is DocType.EXEC and not include_exec:
            continue
        doc_type = node.doc_type.value if node.doc_type else "unknown"
        bucket = grouped.setdefault(doc_type, [])
        if len(bucket) >= limit:
            continue
        bucket.append(
            RecentDocument(
                stem=node.name,
                doc_type=doc_type,
                feature=node.feature,
                modified=recency_string(node),
            )
        )
    return grouped


def _exec_activity(
    nodes: list[DocNode],
    *,
    limit: int,
    since_days: int | None,
    reference: _dt.date,
) -> list[ExecActivity]:
    """Summarise execution records per feature (count plus latest date).

    Execution records are the highest-volume document type, so the rollup
    collapses them to one line per feature instead of listing every step
    record. A *since_days* window filters records first; the result is
    ordered most recently active first and capped at *limit* features.
    """
    cutoff = (
        reference - _dt.timedelta(days=since_days) if since_days is not None else None
    )

    by_feature: dict[str | None, tuple[int, _dt.date]] = {}
    for node in nodes:
        if node.doc_type is not DocType.EXEC:
            continue
        recency = recency_date(node)
        if cutoff is not None and (recency is _NO_DATE or recency < cutoff):
            continue
        count, latest = by_feature.get(node.feature, (0, _NO_DATE))
        by_feature[node.feature] = (count + 1, max(latest, recency))

    ordered = sorted(
        by_feature.items(),
        key=lambda item: (item[1][1], item[0] or ""),
        reverse=True,
    )
    return [
        ExecActivity(
            feature=feature,
            count=count,
            latest=latest.isoformat() if latest is not _NO_DATE else None,
        )
        for feature, (count, latest) in ordered[:limit]
    ]
