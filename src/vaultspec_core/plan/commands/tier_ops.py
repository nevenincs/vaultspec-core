"""Tier show / promote / demote commands (W02.P05.S80-S82).

Per the convention ADR's *Promotion is non-renumbering and
transitive* section, tier promotion adds outer containers without
renumbering existing identifiers. Transitive promotion (``L1`` to
``L4`` in one revision) instantiates intermediate containers with
the next-available identifier in the target sequence.

Per the CLI ADR, ``tier demote`` is refused (exit 1) when the
collapsing tier contains more than one non-retired child container;
``--force`` overrides the refusal and lets the writer accept the
loss explicitly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vaultspec_core.plan.frontmatter import Tier
from vaultspec_core.plan.identifiers import (
    next_available_phase,
    next_available_wave,
)
from vaultspec_core.plan.parser import EpicIntent, Phase, Wave

if TYPE_CHECKING:
    from vaultspec_core.plan.parser import Plan

__all__ = [
    "DemoteError",
    "PromoteError",
    "current_tier",
    "demote_tier",
    "promote_tier",
]


class PromoteError(ValueError):
    """Raised when a promotion call references an unsupported target tier."""


class DemoteError(ValueError):
    """Raised when a demotion would lose information without ``--force``."""


_TIER_ORDER = (Tier.L1, Tier.L2, Tier.L3, Tier.L4)


def current_tier(plan: Plan) -> Tier:
    """Return the plan's declared tier (read-only ``vault plan tier --show``)."""
    return plan.frontmatter.tier


def promote_tier(
    plan: Plan,
    *,
    target: Tier | None = None,
    phase_title: str = "TODO: Phase title",
    phase_intent: str = "TODO: Phase intent paragraph required.",
    wave_title: str = "TODO: Wave title",
    wave_intent: str = "TODO: Wave intent paragraph required.",
    epic_intent: str = "TODO: Epic intent paragraph required.",
) -> Tier:
    """Promote the plan to ``target`` (or one tier up when omitted).

    Promotion is transitive: jumping from ``L1`` to ``L4`` in one call
    is equivalent to applying ``L1->L2->L3->L4`` sequentially. Existing
    identifiers are preserved at every step; intermediate containers
    are instantiated with the next-available identifier in the target
    container's sequence.

    Title and intent arguments fill new containers; missing values
    fall back to ``TODO:`` sentinels that ``vault plan check`` flags.

    Args:
        plan: Parsed :class:`Plan`. Mutated in place.
        target: Target tier; when ``None``, advance one tier.
        phase_title: Title for any newly-instantiated Phase.
        phase_intent: Intent for any newly-instantiated Phase.
        wave_title: Title for any newly-instantiated Wave.
        wave_intent: Intent for any newly-instantiated Wave.
        epic_intent: Intent for the Epic intent block (L4 promotion).

    Returns:
        The new :class:`Tier`.

    Raises:
        PromoteError: When ``target`` is at or below the current tier
            or beyond ``L4``.
    """
    current = plan.frontmatter.tier
    target_tier = target if target is not None else _next_tier(current)
    if target_tier is None:
        msg = f"cannot promote past {current.value}"
        raise PromoteError(msg)
    if _TIER_ORDER.index(target_tier) <= _TIER_ORDER.index(current):
        msg = f"target tier {target_tier.value} is not above current {current.value}"
        raise PromoteError(msg)

    while plan.frontmatter.tier is not target_tier:
        _promote_one_step(
            plan,
            phase_title=phase_title,
            phase_intent=phase_intent,
            wave_title=wave_title,
            wave_intent=wave_intent,
            epic_intent=epic_intent,
        )
    return plan.frontmatter.tier


def demote_tier(
    plan: Plan,
    *,
    target: Tier | None = None,
    force: bool = False,
) -> Tier:
    """Demote the plan to ``target`` (or one tier down when omitted).

    Demotion is refused when the collapsing tier carries more than one
    non-retired child container; ``force=True`` overrides the refusal.

    Args:
        plan: Parsed :class:`Plan`. Mutated in place.
        target: Target tier; when ``None``, demote one tier.
        force: When ``True``, accept the loss of information from
            collapsing multi-child containers.

    Returns:
        The new :class:`Tier`.

    Raises:
        DemoteError: When the multi-child refusal fires without
            ``force=True``, or ``target`` is at or above the current
            tier.
    """
    current = plan.frontmatter.tier
    target_tier = target if target is not None else _previous_tier(current)
    if target_tier is None:
        msg = f"cannot demote below {current.value}"
        raise DemoteError(msg)
    if _TIER_ORDER.index(target_tier) >= _TIER_ORDER.index(current):
        msg = f"target tier {target_tier.value} is not below current {current.value}"
        raise DemoteError(msg)

    while plan.frontmatter.tier is not target_tier:
        _demote_one_step(plan, force=force)
    return plan.frontmatter.tier


# ---- Internals --------------------------------------------------------------


def _next_tier(current: Tier) -> Tier | None:
    index = _TIER_ORDER.index(current)
    if index + 1 >= len(_TIER_ORDER):
        return None
    return _TIER_ORDER[index + 1]


def _previous_tier(current: Tier) -> Tier | None:
    index = _TIER_ORDER.index(current)
    if index == 0:
        return None
    return _TIER_ORDER[index - 1]


def _promote_one_step(
    plan: Plan,
    *,
    phase_title: str,
    phase_intent: str,
    wave_title: str,
    wave_intent: str,
    epic_intent: str,
) -> None:
    """Advance the plan one tier up; preserves existing identifiers."""
    current = plan.frontmatter.tier
    if current is Tier.L1:
        new_phase = Phase(
            canonical_id=next_available_phase(plan),
            display_path="",
            title=phase_title,
            intent=phase_intent,
            steps=list(plan.steps),
        )
        new_phase.display_path = new_phase.canonical_id
        # Recompute Step display paths.
        for step in plan.steps:
            step.display_path = f"{new_phase.canonical_id}.{step.canonical_id}"
        plan.phases = [new_phase]
        plan.frontmatter.tier = Tier.L2
        return
    if current is Tier.L2:
        new_wave = Wave(
            canonical_id=next_available_wave(plan),
            title=wave_title,
            intent=wave_intent,
            phases=list(plan.phases),
        )
        for phase in plan.phases:
            phase.display_path = f"{new_wave.canonical_id}.{phase.canonical_id}"
            for step in phase.steps:
                step.display_path = (
                    f"{new_wave.canonical_id}.{phase.canonical_id}.{step.canonical_id}"
                )
        plan.waves = [new_wave]
        plan.frontmatter.tier = Tier.L3
        return
    if current is Tier.L3:
        plan.epic_intent = EpicIntent(text=epic_intent, line_number=0)
        plan.frontmatter.tier = Tier.L4
        return


def _demote_one_step(plan: Plan, *, force: bool) -> None:
    """Step the plan one tier down; preserves identifiers, refuses on collisions."""
    current = plan.frontmatter.tier
    if current is Tier.L4:
        plan.epic_intent = None
        plan.frontmatter.tier = Tier.L3
        return
    if current is Tier.L3:
        if len(plan.waves) > 1 and not force:
            msg = (
                f"L3 plan has {len(plan.waves)} non-retired Waves; demotion "
                "to L2 collapses the Wave layer and is refused without --force"
            )
            raise DemoteError(msg)
        # Flatten: drop Wave wrapper; phases inherit no Wave parent.
        for phase in plan.phases:
            phase.display_path = phase.canonical_id
            for step in phase.steps:
                step.display_path = f"{phase.canonical_id}.{step.canonical_id}"
        for wave in plan.waves:
            plan.retired_wave_ids.add(wave.canonical_id)
        plan.waves = []
        plan.frontmatter.tier = Tier.L2
        return
    if current is Tier.L2:
        if len(plan.phases) > 1 and not force:
            msg = (
                f"L2 plan has {len(plan.phases)} non-retired Phases; demotion "
                "to L1 collapses the Phase layer and is refused without --force"
            )
            raise DemoteError(msg)
        for step in plan.steps:
            step.display_path = step.canonical_id
        for phase in plan.phases:
            plan.retired_phase_ids.add(phase.canonical_id)
        plan.phases = []
        plan.frontmatter.tier = Tier.L1
        return
