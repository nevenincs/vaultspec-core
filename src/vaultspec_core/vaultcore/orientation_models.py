"""Data model for vault orientation: dataclasses, lifecycle, and recency.

Sibling of :mod:`vaultspec_core.vaultcore.orientation_rollup` and
:mod:`vaultspec_core.vaultcore.orientation_trace`, which compute the two
read-only views (:class:`Rollup` and :class:`GroundingTrace`) built from
the plain dataclasses defined here. This module carries no computation
beyond the pure helpers shared by both views: the lifecycle-status
derivation and the recency (decision D3b) date resolution.

The public surface re-exports every name from
:mod:`vaultspec_core.vaultcore.orientation`; import from there, not this
module, at call sites outside the package.
"""

from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .models import parse_lenient_date

if TYPE_CHECKING:
    from ..graph.api import DocNode

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
    "feature_lifecycle_status",
]


def feature_lifecycle_status(feature: ActiveFeature, doc_types: set[str]) -> str:
    """Derive a feature's lifecycle status from its orientation state.

    The single source of the human lifecycle word the ``find`` MCP tool
    surfaces, sited in the orientation core so the MCP layer performs no
    second inference (the drift class the reconciliation reference
    eliminates). Plan progress is read from the richer :class:`ActiveFeature`
    state (which already folds the parsed plan status), and the document-type
    presence resolves the pre-plan phases:

    - ``In Progress`` - the feature has execution records, or its plan has at
      least one closed step.
    - ``Completed`` - the feature's plan has steps and every step is closed.
    - ``Planned`` - the feature has a plan with no closed steps yet.
    - ``Specified`` - no plan, but an ADR exists.
    - ``Researching`` - no plan or ADR, but research exists.
    - ``Unknown`` - none of the above.

    Args:
        feature: The feature's rollup entry, carrying its plan facts.
        doc_types: The document-type value strings present for the feature
            (e.g. ``{"adr", "plan"}``).

    Returns:
        The lifecycle status word.
    """
    if "exec" in doc_types:
        return "In Progress"
    if feature.has_plan:
        return _plan_lifecycle_status(feature)
    for doc_type, status in _PRE_PLAN_STATUS:
        if doc_type in doc_types:
            return status
    return "Unknown"


def _plan_lifecycle_status(feature: ActiveFeature) -> str:
    """Derive the lifecycle status of a feature that already has a plan."""
    if feature.plan_step_count > 0 and feature.plan_completion_percent >= 100.0:
        return "Completed"
    if feature.plan_steps_completed > 0:
        return "In Progress"
    return "Planned"


#: The pre-plan lifecycle phases in precedence order: the first
#: document type present names the feature's status.
_PRE_PLAN_STATUS: tuple[tuple[str, str], ...] = (
    ("adr", "Specified"),
    ("research", "Researching"),
)


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

    The plan fields aggregate **every** plan document carrying the feature
    tag rather than describing one representative plan: a feature whose
    work is split across several plans reports their combined step totals,
    so neither a completed sibling nor an open one can be masked by the
    plan that happens to be scanned first.

    Attributes:
        name: Feature tag without the leading ``#``.
        doc_count: Number of non-archived documents carrying the tag.
        latest_activity: Canonical ``yyyy-mm-dd`` string of the most
            recent ``modified:``/``date:`` across the feature's
            documents, or ``None`` when no document carries a parseable
            date.
        has_plan: ``True`` when at least one of the feature's documents
            is a plan.
        plan_tier: The highest tier across the feature's readable plans,
            or ``None`` when no plan of the feature parses. Drives the
            condensed plan tail on the active-features row.
        plan_steps_completed: Checked steps summed over the feature's
            readable plans.
        plan_step_count: Total steps summed over the feature's readable
            plans.
        plan_completion_percent: ``plan_steps_completed /
            plan_step_count * 100`` rounded to one decimal place; ``0.0``
            when the feature has no steps.
        plan_count: Number of plan documents carrying the feature tag,
            readable or not, so a reader can tell a single-plan figure
            from a summed one.
        plans_unreadable: Number of those plans that failed to parse and
            therefore contribute no steps. A non-zero count means the
            reported completion covers only part of the feature's plans.
    """

    name: str
    doc_count: int
    latest_activity: str | None
    has_plan: bool
    plan_tier: str | None = None
    plan_steps_completed: int = 0
    plan_step_count: int = 0
    plan_completion_percent: float = 0.0
    plan_count: int = 0
    plans_unreadable: int = 0


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
        exec_missing: Count of checked steps lacking a ledger row.
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
    instead of listing every step record. The per-record listing is
    available on demand via the verbose path.

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
        active_features_total: Features active before the cap. ``status`` is
            the first call of every session, so its largest field is windowed;
            without the total a caller cannot tell a small vault from a
            truncated view.
        limit: The recency limit applied to ``recent_documents`` and to
            ``active_features``.
        since_days: The day-window applied, or ``None`` when the
            count-based default was used.
    """

    active_features: list[ActiveFeature]
    active_features_total: int
    plans_in_flight: list[PlanInFlight]
    recently_completed: list[PlanInFlight]
    recent_documents: dict[str, list[RecentDocument]]
    exec_activity: list[ExecActivity]
    totals: dict[str, Any]
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
        record_stem: The stem of the ledger (or legacy record) mapped to
            this step, or ``None`` for a step with no rows (the explicit
            "no rows" state).
        rows: Count of the step's ledger change rows, or ``None`` when the
            step is mapped by a legacy per-Step record or not at all.
        verify: The step's last ``verify:`` result (``pass`` or ``fail``),
            or ``None`` when no check row exists.
    """

    canonical_id: str
    display_path: str
    checked: bool
    record_stem: str | None
    rows: int | None = None
    verify: str | None = None


@dataclass
class PlanTrace:
    """The grounding trace for a single plan (decision D5).

    Attributes:
        stem: The plan document's filename stem.
        feature: The plan's feature tag without ``#``, or ``None``.
        steps: Per-step ledger mapping in document order.
        unlinked_records: Stems of exec documents that reference this plan
            (graph in-links or ``related:``) yet name no Step: a ledger
            with no rows, or a legacy record without ``step_id:``.
            Surfaced rather than dropped.
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
        exec_missing: Count of checked steps lacking a ledger row.
        error: A parse-error note when the plan could not be parsed,
            otherwise ``None``.
    """

    stem: str
    feature: str | None
    steps: list[StepTrace] = field(default_factory=list)
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
            records, unlinked records, grounding docs) to its
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


def recency_date(node: DocNode) -> _dt.date:
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


def recency_string(node: DocNode) -> str | None:
    """Return a node's canonical ``yyyy-mm-dd`` recency string, or ``None``.

    Args:
        node: The graph node to date.

    Returns:
        Canonical date string, or ``None`` when no source is parseable.
    """
    resolved = recency_date(node)
    return resolved.isoformat() if resolved is not _NO_DATE else None
