"""Plan-document status snapshot.

Computes the structural snapshot reported by ``vaultspec-core vault plan status``: the
declared tier, container counts, completion percentage, and a flag for
the legacy-L2 default. The snapshot has both a structured form
(:class:`PlanStatus`) and a JSON-serialisable dict (built in
:mod:`.commands.status_emitter` once the CLI lands in W02.P02.S43).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from vaultspec_core.plan.frontmatter import Tier
    from vaultspec_core.plan.parser import Plan

__all__ = ["PlanStatus", "collect_status", "status_to_json_dict"]


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
    exec_missing_ids: list[str] = field(default_factory=list)


def collect_status(plan: Plan, root_dir: Path | None = None) -> PlanStatus:
    """Compute a :class:`PlanStatus` snapshot from a parsed plan.

    Args:
        plan: Parsed :class:`vaultspec_core.plan.parser.Plan` model.
        root_dir: Optional project root directory to check for missing
            execution records.

    Returns:
        :class:`PlanStatus` populated from the plan's frontmatter and
        container counts.
    """
    step_count = len(plan.steps)
    steps_completed = sum(1 for step in plan.steps if step.checked)
    completion = (steps_completed / step_count * 100.0) if step_count else 0.0

    exec_missing_ids: list[str] = []
    if root_dir is not None:
        from vaultspec_core.plan.frontmatter import _DIRECTORY_TAGS

        feature = None
        for tag in plan.frontmatter.tags:
            if tag != "#plan" and tag not in _DIRECTORY_TAGS:
                feature = tag.lstrip("#")
                break

        if feature:
            from vaultspec_core.vaultcore.parser import parse_frontmatter
            from vaultspec_core.vaultcore.query import list_documents

            exec_docs = list_documents(root_dir, doc_type="exec", feature=feature)
            scaffolded_step_ids = set()
            for doc in exec_docs:
                try:
                    content = doc.path.read_text(encoding="utf-8")
                    meta, _ = parse_frontmatter(content)
                    step_id = meta.get("step_id")
                    if step_id:
                        scaffolded_step_ids.add(step_id)
                except Exception:
                    pass

            for s in plan.steps:
                if s.checked and s.canonical_id not in scaffolded_step_ids:
                    exec_missing_ids.append(s.canonical_id)

    return PlanStatus(
        tier=plan.frontmatter.tier,
        legacy_tier_default=plan.frontmatter.legacy_tier_default,
        wave_count=len(plan.waves),
        phase_count=len(plan.phases),
        step_count=step_count,
        steps_completed=steps_completed,
        completion_percent=round(completion, 1),
        has_epic_intent=plan.epic_intent is not None,
        exec_missing_ids=exec_missing_ids,
    )


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
        ``has_epic_intent``, ``exec_missing_ids``.
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
        "exec_missing_ids": status.exec_missing_ids,
    }
