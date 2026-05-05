"""Phase-level add and insert commands.

Implements:

- ``add`` (W02.P03.S61): append a Phase at the next-available
  ``P##`` to the tail of the target Wave (or document at L2).
- ``insert`` (W02.P03.S62): place a Phase at a named document
  position (``--before P##`` / ``--after P##``); canonical
  identifier is next-available; parent Wave inferred from anchor.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vaultspec_core.plan.display_path import phase_display_path
from vaultspec_core.plan.frontmatter import Tier
from vaultspec_core.plan.identifiers import next_available_phase
from vaultspec_core.plan.parser import Phase

if TYPE_CHECKING:
    from vaultspec_core.plan.parser import Plan

__all__ = ["AddPhaseError", "add_phase", "insert_phase"]


class AddPhaseError(ValueError):
    """Raised when an add or insert call violates the parent-resolution rule."""


def add_phase(
    plan: Plan,
    *,
    title: str,
    intent: str,
    wave_id: str | None = None,
) -> Phase:
    """Append a Phase at the next-available ``P##`` to the tail of its parent.

    Args:
        plan: Parsed :class:`Plan` model. Mutated in place.
        title: Phase heading title.
        intent: Phase intent paragraph.
        wave_id: Required at ``L3``/``L4``; ignored at ``L2``;
            forbidden at ``L1`` (Phases are not legal there).

    Returns:
        The newly-created :class:`Phase`.

    Raises:
        AddPhaseError: When the parent-resolution rule is violated.
    """
    target_wave = _resolve_wave_for_add(plan, wave_id=wave_id)
    canonical_id = next_available_phase(plan)
    parent_wave_id = target_wave.canonical_id if target_wave is not None else None
    new_phase = Phase(
        canonical_id=canonical_id,
        display_path=phase_display_path(
            phase_id=canonical_id,
            wave_id=parent_wave_id,
        ),
        title=title,
        intent=intent,
        line_number=0,
    )

    plan.phases.append(new_phase)
    if target_wave is not None:
        target_wave.phases.append(new_phase)
    return new_phase


def insert_phase(
    plan: Plan,
    *,
    title: str,
    intent: str,
    before: str | None = None,
    after: str | None = None,
) -> Phase:
    """Place a Phase at a named document position; parent inferred from anchor."""
    if before is None and after is None:
        msg = "insert_phase requires either --before or --after"
        raise AddPhaseError(msg)
    if before is not None and after is not None:
        msg = "insert_phase accepts at most one of --before / --after"
        raise AddPhaseError(msg)

    anchor_id = before if before is not None else after
    assert anchor_id is not None
    anchor_wave, anchor_index = _locate_phase(plan, anchor_id)
    canonical_id = next_available_phase(plan)
    parent_wave_id = anchor_wave.canonical_id if anchor_wave is not None else None
    new_phase = Phase(
        canonical_id=canonical_id,
        display_path=phase_display_path(
            phase_id=canonical_id,
            wave_id=parent_wave_id,
        ),
        title=title,
        intent=intent,
        line_number=0,
    )

    if anchor_wave is None:
        flat_index = next(
            i for i, phase in enumerate(plan.phases) if phase.canonical_id == anchor_id
        )
        position = flat_index if before is not None else flat_index + 1
        plan.phases.insert(position, new_phase)
    else:
        position = anchor_index if before is not None else anchor_index + 1
        anchor_wave.phases.insert(position, new_phase)
        flat_index = next(
            i for i, phase in enumerate(plan.phases) if phase.canonical_id == anchor_id
        )
        flat_position = flat_index if before is not None else flat_index + 1
        plan.phases.insert(flat_position, new_phase)
    return new_phase


def _resolve_wave_for_add(plan: Plan, *, wave_id: str | None):
    """Return the target Wave or ``None`` for L2 plans."""
    tier = plan.frontmatter.tier
    if tier is Tier.L1:
        msg = "L1 plans do not support Phase headings; promote first"
        raise AddPhaseError(msg)
    if tier is Tier.L2:
        if wave_id is not None:
            msg = "L2 plans do not have Waves; --wave must not be set"
            raise AddPhaseError(msg)
        return None
    if wave_id is None:
        msg = (
            f"{tier.value} plans require --wave W##; the parent Wave "
            "cannot be inferred without an anchor."
        )
        raise AddPhaseError(msg)
    for wave in plan.waves:
        if wave.canonical_id == wave_id:
            return wave
    msg = f"wave {wave_id!r} does not exist in this plan"
    raise AddPhaseError(msg)


def _locate_phase(plan: Plan, anchor_id: str):
    """Return (parent Wave or None, index within parent) for ``anchor_id``."""
    if plan.frontmatter.tier is Tier.L2:
        for index, phase in enumerate(plan.phases):
            if phase.canonical_id == anchor_id:
                return None, index
        msg = f"anchor Phase {anchor_id!r} does not exist in this plan"
        raise AddPhaseError(msg)
    for wave in plan.waves:
        for index, phase in enumerate(wave.phases):
            if phase.canonical_id == anchor_id:
                return wave, index
    msg = f"anchor Phase {anchor_id!r} does not exist in this plan"
    raise AddPhaseError(msg)
