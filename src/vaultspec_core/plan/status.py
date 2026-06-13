"""Plan-document status snapshot.

Computes the structural snapshot reported by ``vaultspec-core vault plan status``: the
declared tier, container counts, completion percentage, and a flag for
the legacy-L2 default. The snapshot has both a structured form
(:class:`PlanStatus`) and a JSON-serialisable dict (built in
:mod:`.commands.status_emitter` once the CLI lands in W02.P02.S43).

The module also exposes the batched status core mandated by the
vault-orientation ADR (decision D6): :class:`ExecRecordIndex` scans the
vault's execution records exactly once into a ``(feature, step_id)``
lookup, and :func:`collect_all_statuses` parses every plan once while
sharing that single index. The single-plan :func:`collect_status` path
is refactored to consume the same shared index so both surfaces run the
same core rather than re-scanning per call.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from vaultspec_core.plan.frontmatter import Tier
    from vaultspec_core.plan.parser import Plan
    from vaultspec_core.vaultcore.query import VaultDocument

__all__ = [
    "ExecRecordIndex",
    "PlanStatus",
    "PlanStatusEntry",
    "collect_all_statuses",
    "collect_status",
    "status_to_json_dict",
]


@dataclass
class PlanStatus:
    """Structured snapshot of a plan document.

    Attributes:
        tier: The declared (or defaulted) complexity tier.
        legacy_tier_default: ``True`` when the document lacked a
            ``tier:`` field and the parser applied the L2 default.
        wave_count: Number of Waves at L3/L4; ``0`` at L1/L2.
        phase_count: Number of Phases at L2/L3/L4; ``0`` at L1.
        step_count: Total number of Step rows in the plan.
        steps_completed: Number of Steps with ``- [x]`` checkbox.
        completion_percent: ``steps_completed / step_count * 100``,
            rounded to one decimal place. ``0.0`` when ``step_count``
            is zero.
        has_epic_intent: ``True`` when an L4 plan declares its Epic
            intent block.
        waves_completed: Number of Waves whose every Step is checked; ``0``
            at L1/L2 (no Waves) or when no Wave is fully closed.
        phases_completed: Number of Phases whose every Step is checked;
            ``0`` at L1 (no Phases) or when no Phase is fully closed.
        next_open_step: The tier-conditional display path of the first
            unchecked Step in document order (the "you are here" cursor),
            or ``None`` when the plan has no open steps.
        exec_missing_ids: Canonical IDs of checked steps lacking an execution
            record.
    """

    tier: Tier
    legacy_tier_default: bool
    wave_count: int
    phase_count: int
    step_count: int
    steps_completed: int
    completion_percent: float
    has_epic_intent: bool
    waves_completed: int
    phases_completed: int
    next_open_step: str | None
    exec_missing_ids: list[str] = field(default_factory=list)


@dataclass
class ExecRecordIndex:
    """Shared one-pass index of execution records keyed by step.

    Built once from a single ``list_documents(doc_type="exec")`` scan
    (decision D6), this index maps every scaffolded execution record to
    its originating Step so a plan's missing-record check is a dict
    lookup rather than a per-plan exec rescan. Both the single-plan
    :func:`collect_status` path and the batched
    :func:`collect_all_statuses` path consume the same instance.

    Attributes:
        by_step: Map from ``(feature, step_id)`` to the execution
            record's filename stem. A record whose ``step_id:``
            frontmatter is absent is recorded under
            :attr:`unlinked_by_feature` instead.
        unlinked_by_feature: Map from feature to the stems of execution
            records that carry no resolvable ``step_id:`` frontmatter,
            so the orientation trace can surface them rather than drop
            them silently (the unlinked bucket of decision D5).
    """

    by_step: dict[tuple[str, str], str] = field(default_factory=dict)
    unlinked_by_feature: dict[str, list[str]] = field(default_factory=dict)

    @classmethod
    def build(cls, root_dir: Path) -> ExecRecordIndex:
        """Scan every execution record once into the shared index.

        Args:
            root_dir: Project root directory.

        Returns:
            A populated :class:`ExecRecordIndex`. Records whose feature
            tag or ``step_id:`` cannot be read are bucketed as unlinked
            under their best-known feature rather than aborting the scan.
        """
        from vaultspec_core.vaultcore.parser import parse_frontmatter
        from vaultspec_core.vaultcore.query import list_documents

        index = cls()
        for doc in list_documents(root_dir, doc_type="exec"):
            feature = doc.feature
            step_id: str | None = None
            try:
                content = doc.path.read_text(encoding="utf-8")
                meta, _ = parse_frontmatter(content)
                raw_step_id = meta.get("step_id")
                if raw_step_id:
                    step_id = str(raw_step_id).strip()
            except (OSError, UnicodeDecodeError):
                pass

            if feature and step_id:
                index.by_step[(feature, step_id)] = doc.name
            elif feature:
                index.unlinked_by_feature.setdefault(feature, []).append(doc.name)
        return index

    def record_for(self, feature: str, step_id: str) -> str | None:
        """Return the execution-record stem mapped to a Step, or ``None``.

        Args:
            feature: Feature tag (without ``#``).
            step_id: Canonical Step identifier (e.g. ``S01``).

        Returns:
            The execution record's stem, or ``None`` when no scaffolded
            record references that Step.
        """
        return self.by_step.get((feature, step_id))


def _plan_feature(plan: Plan) -> str | None:
    """Return the plan's feature tag without ``#``, or ``None``.

    The feature is the first tag that is neither ``#plan`` nor any other
    canonical directory tag, matching the single-feature-tag schema rule.

    Args:
        plan: Parsed :class:`Plan` model.

    Returns:
        Feature name string, or ``None`` when the plan carries none.
    """
    from vaultspec_core.plan.frontmatter import _DIRECTORY_TAGS

    for tag in plan.frontmatter.tags:
        if tag != "#plan" and tag not in _DIRECTORY_TAGS:
            return tag.lstrip("#")
    return None


def _container_completion(plan: Plan) -> tuple[int, int, str | None]:
    """Derive per-container completion and the first-open-step cursor.

    All three facts come from the already-parsed container chains
    (:attr:`Plan.waves`, :attr:`Plan.phases`, :attr:`Plan.steps`); no
    rescan or extra traversal is performed, so this stays inside the
    single batched status pass.

    A Wave or Phase counts as completed only when it holds at least one
    Step and every Step it holds is checked, so an empty container is
    never miscounted as done. The cursor is the first unchecked Step in
    document order, reported as its tier-conditional display path.

    Args:
        plan: Parsed :class:`Plan` model.

    Returns:
        A ``(waves_completed, phases_completed, next_open_step)`` tuple.
    """
    waves_completed = 0
    for wave in plan.waves:
        wave_steps = [step for phase in wave.phases for step in phase.steps]
        if wave_steps and all(step.checked for step in wave_steps):
            waves_completed += 1

    phases_completed = sum(
        1
        for phase in plan.phases
        if phase.steps and all(step.checked for step in phase.steps)
    )

    next_open_step = next(
        (step.display_path for step in plan.steps if not step.checked), None
    )
    return waves_completed, phases_completed, next_open_step


def collect_status(
    plan: Plan,
    root_dir: Path | None = None,
    *,
    exec_index: ExecRecordIndex | None = None,
) -> PlanStatus:
    """Compute a :class:`PlanStatus` snapshot from a parsed plan.

    Args:
        plan: Parsed :class:`vaultspec_core.plan.parser.Plan` model.
        root_dir: Optional project root directory used to build the
            shared execution-record index when *exec_index* is not
            supplied. Ignored when *exec_index* is given.
        exec_index: Optional pre-built :class:`ExecRecordIndex`. When
            supplied (the batched path), the per-call exec scan is
            skipped entirely and this index is reused; this is the shared
            core mandated by decision D6. When omitted but *root_dir* is
            given, a fresh single-plan index is built.

    Returns:
        :class:`PlanStatus` populated from the plan's frontmatter and
        container counts.
    """
    step_count = len(plan.steps)
    steps_completed = sum(1 for step in plan.steps if step.checked)
    completion = (steps_completed / step_count * 100.0) if step_count else 0.0

    exec_missing_ids: list[str] = []
    index = exec_index
    if index is None and root_dir is not None:
        index = ExecRecordIndex.build(root_dir)

    if index is not None:
        feature = _plan_feature(plan)
        if feature:
            for step in plan.steps:
                if (
                    step.checked
                    and index.record_for(feature, step.canonical_id) is None
                ):
                    exec_missing_ids.append(step.canonical_id)

    waves_completed, phases_completed, next_open_step = _container_completion(plan)

    return PlanStatus(
        tier=plan.frontmatter.tier,
        legacy_tier_default=plan.frontmatter.legacy_tier_default,
        wave_count=len(plan.waves),
        phase_count=len(plan.phases),
        step_count=step_count,
        steps_completed=steps_completed,
        completion_percent=round(completion, 1),
        has_epic_intent=plan.epic_intent is not None,
        waves_completed=waves_completed,
        phases_completed=phases_completed,
        next_open_step=next_open_step,
        exec_missing_ids=exec_missing_ids,
    )


@dataclass
class PlanStatusEntry:
    """One plan's batched status result from :func:`collect_all_statuses`.

    Attributes:
        document: The :class:`~vaultspec_core.vaultcore.query.VaultDocument`
            for the plan, carrying its stem, path, feature, and dates.
        plan: The parsed :class:`Plan`, or ``None`` when the plan could
            not be parsed.
        status: The computed :class:`PlanStatus`, or ``None`` when the
            plan could not be parsed.
        error: A human-readable parse-error note when *plan* is ``None``,
            otherwise ``None``. An unparseable plan is collected with this
            note rather than aborting the batch.
    """

    document: VaultDocument
    plan: Plan | None
    status: PlanStatus | None
    error: str | None = None


def collect_all_statuses(root_dir: Path) -> list[PlanStatusEntry]:
    """Collect status for every plan in the vault in one batched pass.

    Implements the batched status core (decision D6): the execution
    records are scanned once into a shared :class:`ExecRecordIndex`, every
    plan document is parsed once, and each plan's status is computed
    against the shared index. An individual plan that fails to parse is
    collected as a :class:`PlanStatusEntry` carrying an ``error`` note,
    so one malformed plan never aborts the whole rollup.

    Args:
        root_dir: Project root directory.

    Returns:
        A list of :class:`PlanStatusEntry`, one per plan document, in the
        order :func:`~vaultspec_core.vaultcore.query.list_documents`
        returns them.
    """
    from vaultspec_core.plan.parser import parse_plan
    from vaultspec_core.vaultcore.query import list_documents

    exec_index = ExecRecordIndex.build(root_dir)
    entries: list[PlanStatusEntry] = []
    for doc in list_documents(root_dir, doc_type="plan"):
        try:
            content = doc.path.read_text(encoding="utf-8")
            plan = parse_plan(content)
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            entries.append(
                PlanStatusEntry(
                    document=doc,
                    plan=None,
                    status=None,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
            continue
        status = collect_status(plan, exec_index=exec_index)
        entries.append(PlanStatusEntry(document=doc, plan=plan, status=status))
    return entries


def status_to_json_dict(status: PlanStatus) -> dict[str, object]:
    """Convert a :class:`PlanStatus` to a JSON-serialisable dict.

    The schema is fixed for downstream tools (CI dashboards, IDE
    integrations) so changes to it are a contract change. Field names
    are snake_case; the ``tier`` enum is rendered as its string value.

    Args:
        status: Snapshot returned by :func:`collect_status`.

    Returns:
        Dict with keys ``tier``, ``legacy_tier_default``,
        ``wave_count``, ``phase_count``, ``step_count``,
        ``steps_completed``, ``completion_percent``,
        ``has_epic_intent``, ``waves_completed``, ``phases_completed``,
        ``next_open_step``, ``exec_missing_ids``.
    """
    return {
        "tier": status.tier.value,
        "legacy_tier_default": status.legacy_tier_default,
        "wave_count": status.wave_count,
        "phase_count": status.phase_count,
        "step_count": status.step_count,
        "steps_completed": status.steps_completed,
        "completion_percent": status.completion_percent,
        "has_epic_intent": status.has_epic_intent,
        "waves_completed": status.waves_completed,
        "phases_completed": status.phases_completed,
        "next_open_step": status.next_open_step,
        "exec_missing_ids": status.exec_missing_ids,
    }
