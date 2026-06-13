"""Vault orientation rollup and grounding-trace data layer.

This is the pure data core behind ``vaultspec-core status`` (the
vault-orientation ADR's decisions D2, D4, D5, and D6). It computes two
read-only views and prints nothing: the CLI verb in the next phase
renders these structures directly, so every field is pre-shaped (stems,
display paths, counts, percentages) and needs no recomputation at render
time.

- :func:`compute_rollup` returns the vault-wide :class:`Rollup`: active
  (non-archived) features ordered by latest activity, plans in flight
  with open/closed counts and completion percent, recently modified
  documents grouped by type, and totals echoing
  :func:`~vaultspec_core.vaultcore.query.get_stats` (decisions D2/D4).
- :func:`compute_trace` returns the targeted :class:`GroundingTrace`:
  for a plan stem, plan path, or feature tag, each plan's steps mapped to
  their execution-record stems (or ``None`` for open steps without a
  record, or the explicit unlinked bucket for records that reference the
  plan without a resolvable step id), plus grounding documents grouped by
  type from the plan's graph neighbours (decision D5).

Recency follows decision D3b: each document's sort key is its leniently
parsed ``modified:`` stamp, falling back to ``date:``, then to the
filename date prefix; a document with no parseable date sorts last and
never crashes the rollup.

The graph is used internally for traceback (decision D5) but never leaks
into the output: every returned structure is a plain dataclass of stems
and scalars, with no ``networkx`` types, node objects, or edge lists.
"""

from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .models import DocType, parse_lenient_date

if TYPE_CHECKING:
    from pathlib import Path

    from ..graph.api import DocNode, VaultGraph
    from ..plan.status import ExecRecordIndex, PlanStatus, PlanStatusEntry

__all__ = [
    "ActiveFeature",
    "ExecActivity",
    "GroundingTrace",
    "PlanInFlight",
    "PlanTrace",
    "RecentDocument",
    "Rollup",
    "StepTrace",
    "TargetResolutionError",
    "compute_rollup",
    "compute_trace",
]


#: ``yyyy-mm-dd`` prefix on a vault filename stem, the third recency
#: fallback after ``modified:`` and ``date:`` (decision D3b).
_FILENAME_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")

#: Sentinel ordinal for a document with no parseable date: it sorts after
#: every dated document under a descending (most-recent-first) sort
#: without crashing the comparison (decision D3b).
_NO_DATE = _dt.date.min


# ---------------------------------------------------------------------------
# Rollup data model (decisions D2 / D4)
# ---------------------------------------------------------------------------


@dataclass
class ActiveFeature:
    """One non-archived feature in the rollup, with its latest activity.

    Attributes:
        name: Feature tag without the leading ``#``.
        doc_count: Number of non-archived documents carrying the tag.
        latest_activity: Canonical ``yyyy-mm-dd`` string of the most
            recent ``modified:``/``date:`` across the feature's
            documents, or ``None`` when no document carries a parseable
            date.
        has_plan: ``True`` when at least one of the feature's documents
            is a plan.
        plan_tier: The feature's plan tier value, or ``None`` when the
            feature has no parseable plan. Drives the condensed plan tail
            on the active-features row.
        plan_steps_completed: Checked-step count of the feature's plan.
        plan_step_count: Total step count of the feature's plan.
        plan_completion_percent: Completion percent of the feature's plan.
    """

    name: str
    doc_count: int
    latest_activity: str | None
    has_plan: bool
    plan_tier: str | None = None
    plan_steps_completed: int = 0
    plan_step_count: int = 0
    plan_completion_percent: float = 0.0


@dataclass
class PlanInFlight:
    """A plan with at least one open step, pre-shaped for rendering.

    Attributes:
        stem: The plan document's filename stem.
        feature: The plan's feature tag without ``#``, or ``None``.
        tier: The declared (or defaulted) complexity tier value
            (``"L1"`` .. ``"L4"``), used to gate wave/phase columns.
        open_steps: Number of unchecked steps.
        closed_steps: Number of checked steps.
        total_steps: Total step count.
        completion_percent: ``closed_steps / total_steps * 100`` rounded
            to one decimal place.
        wave_count: Total number of Waves; ``0`` at L1/L2.
        waves_completed: Number of fully-checked Waves.
        phase_count: Total number of Phases; ``0`` at L1.
        phases_completed: Number of fully-checked Phases.
        next_open_step: Display path of the first open step (the cursor),
            or ``None`` when the plan has no open steps.
        exec_missing: Count of checked steps lacking an execution record.
        modified: Canonical ``yyyy-mm-dd`` recency string used for
            ordering, or ``None`` when no parseable date exists.
    """

    stem: str
    feature: str | None
    tier: str
    open_steps: int
    closed_steps: int
    total_steps: int
    completion_percent: float
    wave_count: int
    waves_completed: int
    phase_count: int
    phases_completed: int
    next_open_step: str | None
    exec_missing: int
    modified: str | None


@dataclass
class RecentDocument:
    """A recently modified document, rendered as a stem plus its recency.

    Attributes:
        stem: The document's filename stem.
        doc_type: The document type value (e.g. ``"plan"``), or
            ``"unknown"``.
        feature: The feature tag without ``#``, or ``None``.
        modified: Canonical ``yyyy-mm-dd`` recency string, or ``None``
            when no parseable date exists.
    """

    stem: str
    doc_type: str
    feature: str | None
    modified: str | None


@dataclass
class ExecActivity:
    """Collapsed execution activity for one feature.

    Execution records are the highest-volume document type, so the rollup
    summarises them per feature - a count and the latest activity date -
    instead of listing every step record and drowning the recent view. The
    per-record listing is available on demand via the verbose path.

    Attributes:
        feature: Feature tag without ``#``, or ``None`` for records that
            carry no feature.
        count: Number of execution records for the feature within the
            active recency window.
        latest: Canonical ``yyyy-mm-dd`` of the most recent record, or
            ``None`` when none carries a parseable date.
    """

    feature: str | None
    count: int
    latest: str | None


@dataclass
class Rollup:
    """The vault-wide orientation rollup (decisions D2/D4).

    Every field is pre-computed so the CLI renderer needs no further
    work: counts, percentages, ordering, and grouping are all settled
    here.

    Attributes:
        active_features: Non-archived features ordered by latest activity
            descending (most recently active first).
        plans_in_flight: Plans with at least one open step, ordered most
            recently modified first.
        recently_completed: Plans at 100% completion, ordered most recently
            modified first and capped, so a just-finished plan stays visible
            in the rollup rather than silently vanishing.
        recent_documents: Recently modified documents grouped by document
            type, each group capped to ``limit`` and ordered most recent
            first. Execution records are excluded here unless the verbose
            path is taken; they are summarised by ``exec_activity``.
        exec_activity: Per-feature execution-record summaries (count plus
            latest date), so the high-volume exec type never floods the
            recent view. Empty when the verbose path lists exec records in
            ``recent_documents`` instead.
        totals: The dict returned by
            :func:`~vaultspec_core.vaultcore.query.get_stats`, reused
            verbatim so the rollup echoes the established stats surface.
        limit: The recency limit applied to ``recent_documents``.
        since_days: The day-window applied, or ``None`` when the
            count-based default was used.
    """

    active_features: list[ActiveFeature]
    plans_in_flight: list[PlanInFlight]
    recently_completed: list[PlanInFlight]
    recent_documents: dict[str, list[RecentDocument]]
    exec_activity: list[ExecActivity]
    totals: dict
    limit: int
    since_days: int | None


# ---------------------------------------------------------------------------
# Grounding-trace data model (decision D5)
# ---------------------------------------------------------------------------


@dataclass
class StepTrace:
    """One plan step mapped to its execution record (decision D5).

    Attributes:
        canonical_id: The step's canonical leaf identifier (``S##``).
        display_path: The step's tier-conditional display path.
        checked: ``True`` when the step's checkbox is ``[x]``.
        record_stem: The execution-record stem mapped to this step, or
            ``None`` for an open step with no record (the explicit
            "no record" state).
    """

    canonical_id: str
    display_path: str
    checked: bool
    record_stem: str | None


@dataclass
class PlanTrace:
    """The grounding trace for a single plan (decision D5).

    Attributes:
        stem: The plan document's filename stem.
        feature: The plan's feature tag without ``#``, or ``None``.
        steps: Per-step record mapping in document order.
        summaries: Stems of phase-summary documents (``-summary`` suffix)
            that reference this plan. Summaries carry no ``step_id:`` by
            design, so they are grouped here instead of being misreported
            as unlinked anomalies.
        unlinked_records: Stems of execution records that reference this
            plan (graph in-links or ``related:``) without a resolvable
            ``step_id:``, surfaced rather than dropped.
        grounding: Grounding documents grouped by document type, drawn
            from the plan's outgoing ``related:`` neighbours (adr,
            research, reference, prior plan) and incoming non-exec
            references. Stems only.
        tier: The plan's tier value, or ``None`` when unparsed; drives the
            clean plan-line header.
        total_steps: Total step count.
        closed_steps: Checked-step count.
        open_steps: Unchecked-step count.
        completion_percent: Completion percent.
        wave_count: Total Waves; ``0`` at L1/L2.
        waves_completed: Fully-checked Waves.
        phase_count: Total Phases; ``0`` at L1.
        phases_completed: Fully-checked Phases.
        next_open_step: Display path of the first open step (the cursor),
            or ``None`` when complete.
        exec_missing: Count of checked steps lacking an execution record.
        error: A parse-error note when the plan could not be parsed,
            otherwise ``None``.
    """

    stem: str
    feature: str | None
    steps: list[StepTrace] = field(default_factory=list)
    summaries: list[str] = field(default_factory=list)
    unlinked_records: list[str] = field(default_factory=list)
    grounding: dict[str, list[str]] = field(default_factory=dict)
    tier: str | None = None
    total_steps: int = 0
    closed_steps: int = 0
    open_steps: int = 0
    completion_percent: float = 0.0
    wave_count: int = 0
    waves_completed: int = 0
    phase_count: int = 0
    phases_completed: int = 0
    next_open_step: str | None = None
    exec_missing: int = 0
    error: str | None = None


@dataclass
class GroundingTrace:
    """The resolved grounding trace for a target (decision D5).

    Attributes:
        target: The raw target string the caller supplied.
        kind: How the target resolved: ``"plan"`` (a single plan stem or
            path) or ``"feature"`` (a feature tag matching one or more
            plans).
        plans: One :class:`PlanTrace` per plan under the target, in stem
            order.
        paths: Map from every referenced document stem (plans, step
            records, summaries, unlinked records, grounding docs) to its
            repo-relative path, so file discovery yields openable paths
            without leaking the graph. Empty unless paths
            were requested.
    """

    target: str
    kind: str
    plans: list[PlanTrace]
    paths: dict[str, str] = field(default_factory=dict)


class TargetResolutionError(ValueError):
    """Raised when a trace target is ambiguous or unknown.

    Carries the near-matches so the CLI can render an actionable hint
    rather than a bare failure.

    Attributes:
        target: The raw target string that could not be resolved.
        near_matches: Stems or feature tags that resemble the target,
            offered as suggestions.
    """

    def __init__(self, target: str, near_matches: list[str]) -> None:
        self.target = target
        self.near_matches = near_matches
        suggestion = (
            f" Did you mean: {', '.join(near_matches)}?"
            if near_matches
            else (
                " Run `vaultspec-core vault feature list` to enumerate"
                " available targets."
            )
        )
        super().__init__(
            f"Could not resolve orientation target {target!r}.{suggestion}"
        )


# ---------------------------------------------------------------------------
# Recency (decision D3b)
# ---------------------------------------------------------------------------


def _recency_date(node: DocNode) -> _dt.date:
    """Return a node's recency date for sorting, never raising.

    Parses ``modified:`` leniently, falls back to ``date:``, then to the
    filename date prefix; a node with no parseable date returns
    :data:`_NO_DATE` so it sorts last under a most-recent-first order
    (decision D3b).

    Args:
        node: The graph node to date.

    Returns:
        The resolved :class:`datetime.date`, or :data:`_NO_DATE` when no
        source is parseable.
    """
    for raw in (node.modified, node.date):
        parsed = parse_lenient_date(raw)
        if parsed is not None:
            return parsed
    match = _FILENAME_DATE_RE.match(node.name)
    if match:
        parsed = parse_lenient_date(match.group(1))
        if parsed is not None:
            return parsed
    return _NO_DATE


def _recency_string(node: DocNode) -> str | None:
    """Return a node's canonical ``yyyy-mm-dd`` recency string, or ``None``.

    Args:
        node: The graph node to date.

    Returns:
        Canonical date string, or ``None`` when no source is parseable.
    """
    resolved = _recency_date(node)
    return resolved.isoformat() if resolved is not _NO_DATE else None


# ---------------------------------------------------------------------------
# Rollup (decisions D2 / D4 / D6)
# ---------------------------------------------------------------------------


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
    entries = collect_all_statuses(root_dir)
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
    totals = get_stats(root_dir)

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
        latest = max(_recency_date(n) for n in feat_nodes)
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
        recency = _recency_date(node) if node is not None else _NO_DATE
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
        ((node, _recency_date(node)) for node in nodes),
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
                modified=_recency_string(node),
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
        recency = _recency_date(node)
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


# ---------------------------------------------------------------------------
# Grounding trace (decision D5)
# ---------------------------------------------------------------------------

#: Document types that count as grounding context for a plan; everything
#: else (notably ``exec``) is handled by the step-to-record mapping and
#: the unlinked bucket rather than the grounding grouping.
_GROUNDING_TYPES = frozenset(
    {
        DocType.ADR.value,
        DocType.RESEARCH.value,
        DocType.REFERENCE.value,
        DocType.PLAN.value,
        DocType.AUDIT.value,
    }
)


def compute_trace(
    root_dir: Path,
    target: str,
    *,
    graph: VaultGraph | None = None,
    with_paths: bool = False,
) -> GroundingTrace:
    """Compute the grounding trace for a target (decision D5).

    Target resolution precedence is exact plan stem, then plan path,
    then feature tag. An ambiguous or unknown target raises
    :class:`TargetResolutionError` carrying near-matches.

    Args:
        root_dir: Project root directory.
        target: A plan stem, a plan path, or a feature tag (with or
            without the leading ``#``).
        graph: Optional pre-built :class:`~vaultspec_core.graph.VaultGraph`
            to reuse; one is built from *root_dir* when omitted.
        with_paths: When ``True``, populate :attr:`GroundingTrace.paths`
            with the repo-relative path of every referenced document stem
            so file discovery yields openable paths.

    Returns:
        A :class:`GroundingTrace` with one :class:`PlanTrace` per plan
        under the resolved target.

    Raises:
        TargetResolutionError: When the target resolves to no plan or
            feature.
    """
    from ..graph.api import VaultGraph
    from ..plan.status import ExecRecordIndex

    g = graph if graph is not None else VaultGraph(root_dir)
    exec_index = ExecRecordIndex.build(root_dir)

    plan_stems = {
        name
        for name, node in g.nodes.items()
        if not node.phantom and node.doc_type is DocType.PLAN
    }

    kind, stems = _resolve_target(target, plan_stems, g)

    plans = [_plan_trace(g, exec_index, stem) for stem in sorted(stems)]
    paths = _trace_paths(g, root_dir, plans) if with_paths else {}
    return GroundingTrace(target=target, kind=kind, plans=plans, paths=paths)


def _trace_paths(
    graph: VaultGraph,
    root_dir: Path,
    plans: list[PlanTrace],
) -> dict[str, str]:
    """Map every stem a trace references to its repo-relative path.

    Sources every plan stem, step record, summary, unlinked record, and
    grounding stem, resolving each through its graph node's backing path.
    Stems with no backing file (phantom or pathless) are omitted rather
    than mapped to a fabricated path. The graph stays internal (decision
    D5/D7); only plain relative-path strings leave this function.
    """
    stems: set[str] = set()
    for plan in plans:
        stems.add(plan.stem)
        stems.update(step.record_stem for step in plan.steps if step.record_stem)
        stems.update(plan.summaries)
        stems.update(plan.unlinked_records)
        for grounded in plan.grounding.values():
            stems.update(grounded)

    paths: dict[str, str] = {}
    for stem in stems:
        node = graph.nodes.get(stem)
        if node is None or node.path is None:
            continue
        try:
            rel = node.path.resolve().relative_to(root_dir.resolve())
        except ValueError:
            rel = node.path
        paths[stem] = rel.as_posix()
    return paths


def _resolve_target(
    target: str,
    plan_stems: set[str],
    graph: VaultGraph,
) -> tuple[str, set[str]]:
    """Resolve a trace target to a kind plus the set of plan stems.

    Precedence: exact plan stem > plan path > feature tag.
    """
    from pathlib import Path as _Path

    cleaned = target.strip()

    # 1. Exact plan stem.
    if cleaned in plan_stems:
        return "plan", {cleaned}

    # 2. Plan path (absolute or relative; with or without .md).
    path_stem = _Path(cleaned).stem
    if path_stem in plan_stems and (
        "/" in cleaned or "\\" in cleaned or cleaned.endswith(".md")
    ):
        return "plan", {path_stem}

    # 3. Feature tag (with or without leading '#').
    feature = cleaned.lstrip("#")
    feature_plans = {
        name for name in plan_stems if graph.nodes[name].feature == feature
    }
    if feature_plans:
        return "feature", feature_plans

    near = _near_matches(cleaned, plan_stems, graph)
    raise TargetResolutionError(target, near)


def _near_matches(
    target: str,
    plan_stems: set[str],
    graph: VaultGraph,
) -> list[str]:
    """Return up to five plausible target suggestions for an unknown target.

    Suggestions are plan stems or feature tags containing the target as a
    case-insensitive substring, sorted for a stable order.
    """
    needle = target.lstrip("#").lower()
    matches: set[str] = set()
    for stem in plan_stems:
        if needle and needle in stem.lower():
            matches.add(stem)
        feature = graph.nodes[stem].feature
        if feature and needle and needle in feature.lower():
            matches.add(f"#{feature}")
    return sorted(matches)[:5]


def _plan_trace(
    graph: VaultGraph,
    exec_index: ExecRecordIndex,
    stem: str,
) -> PlanTrace:
    """Build the :class:`PlanTrace` for a single plan stem (decision D5)."""
    from ..plan.parser import parse_plan
    from ..plan.status import collect_status

    node = graph.nodes[stem]
    feature = node.feature

    if node.path is None:
        return PlanTrace(stem=stem, feature=feature, error="plan has no backing file")

    try:
        plan = parse_plan(node.path)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return PlanTrace(
            stem=stem,
            feature=feature,
            error=f"{type(exc).__name__}: {exc}",
        )

    steps: list[StepTrace] = []
    matched_records: set[str] = set()
    for step in plan.steps:
        record_stem = (
            exec_index.record_for(feature, step.canonical_id) if feature else None
        )
        if record_stem is not None:
            matched_records.add(record_stem)
        steps.append(
            StepTrace(
                canonical_id=step.canonical_id,
                display_path=step.display_path,
                checked=step.checked,
                record_stem=record_stem,
            )
        )

    referencing = _unlinked_records(graph, exec_index, stem, feature, matched_records)
    summaries = [s for s in referencing if s.endswith("-summary")]
    unlinked = [s for s in referencing if not s.endswith("-summary")]
    grounding = _grounding_documents(graph, stem)

    # Reuse the batched status core so the trace header carries the same
    # clean plan-line facts the rollup shows.
    status = collect_status(plan, exec_index=exec_index)

    return PlanTrace(
        stem=stem,
        feature=feature,
        steps=steps,
        summaries=summaries,
        unlinked_records=unlinked,
        grounding=grounding,
        tier=status.tier.value,
        total_steps=status.step_count,
        closed_steps=status.steps_completed,
        open_steps=status.step_count - status.steps_completed,
        completion_percent=status.completion_percent,
        wave_count=status.wave_count,
        waves_completed=status.waves_completed,
        phase_count=status.phase_count,
        phases_completed=status.phases_completed,
        next_open_step=status.next_open_step,
        exec_missing=len(status.exec_missing_ids),
    )


def _unlinked_records(
    graph: VaultGraph,
    exec_index: ExecRecordIndex,
    stem: str,
    feature: str | None,
    matched_records: set[str],
) -> list[str]:
    """Return exec records that reference the plan but map to no step.

    Two sources contribute (decision D5): the feature's records whose
    ``step_id:`` was absent (the index's unlinked bucket), and any exec
    record that links to the plan (graph in-link or ``related:``) yet did
    not map to a step. Records already matched to a step are excluded.
    """
    candidates: set[str] = set()

    if feature:
        for record in exec_index.unlinked_by_feature.get(feature, []):
            candidates.add(record)

    node = graph.nodes[stem]
    for src in node.in_links:
        src_node = graph.nodes.get(src)
        if (
            src_node is not None
            and src_node.doc_type is DocType.EXEC
            and src not in matched_records
        ):
            candidates.add(src)

    return sorted(candidates - matched_records)


def _grounding_documents(graph: VaultGraph, stem: str) -> dict[str, list[str]]:
    """Group the plan's grounding neighbours by document type (decision D5).

    Outgoing ``related:`` neighbours (adr, research, reference, prior
    plan, audit) plus incoming non-exec references are collected as
    stems and grouped by type. Exec in-links are deliberately excluded
    here; they are the step-to-record concern.
    """
    node = graph.nodes[stem]
    grouped: dict[str, set[str]] = {}

    def _add(neighbour_name: str) -> None:
        neighbour = graph.nodes.get(neighbour_name)
        if neighbour is None or neighbour.phantom or neighbour.doc_type is None:
            return
        if neighbour_name == stem:
            return
        doc_type = neighbour.doc_type.value
        if doc_type not in _GROUNDING_TYPES:
            return
        grouped.setdefault(doc_type, set()).add(neighbour_name)

    for out in node.out_links:
        _add(out)
    for inc in node.in_links:
        _add(inc)

    return {doc_type: sorted(stems) for doc_type, stems in sorted(grouped.items())}
