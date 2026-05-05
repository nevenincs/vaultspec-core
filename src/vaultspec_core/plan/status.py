"""Plan-document status snapshot.

Computes the structural snapshot reported by ``vault plan status``: the
declared tier, container counts, completion percentage, and a flag for
the legacy-L2 default. The snapshot has both a structured form
(:class:`PlanStatus`) and a JSON-serialisable dict (built in
:mod:`.commands.status_emitter` once the CLI lands in W02.P02.S43).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vaultspec_core.plan.frontmatter import Tier
    from vaultspec_core.plan.parser import Plan

__all__ = ["PlanStatus", "collect_status"]


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
    """

    tier: Tier
    legacy_tier_default: bool
    wave_count: int
    phase_count: int
    step_count: int
    steps_completed: int
    completion_percent: float
    has_epic_intent: bool


def collect_status(plan: Plan) -> PlanStatus:
    """Compute a :class:`PlanStatus` snapshot from a parsed plan.

    Args:
        plan: Parsed :class:`vaultspec_core.plan.parser.Plan` model.

    Returns:
        :class:`PlanStatus` populated from the plan's frontmatter and
        container counts.
    """
    step_count = len(plan.steps)
    steps_completed = sum(1 for step in plan.steps if step.checked)
    completion = (steps_completed / step_count * 100.0) if step_count else 0.0
    return PlanStatus(
        tier=plan.frontmatter.tier,
        legacy_tier_default=plan.frontmatter.legacy_tier_default,
        wave_count=len(plan.waves),
        phase_count=len(plan.phases),
        step_count=step_count,
        steps_completed=steps_completed,
        completion_percent=round(completion, 1),
        has_epic_intent=plan.epic_intent is not None,
    )
