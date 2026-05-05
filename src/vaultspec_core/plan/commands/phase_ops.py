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

__all__ = [
    "AddPhaseError",
    "MovePhaseError",
    "PhaseNotFoundError",
    "add_phase",
    "edit_phase",
    "find_phase",
    "insert_phase",
    "move_phase",
    "remove_phase",
]


class AddPhaseError(ValueError):
    """Raised when an add or insert call violates the parent-resolution rule."""


class PhaseNotFoundError(KeyError):
    """Raised when a Phase canonical identifier does not exist in the plan."""


class MovePhaseError(ValueError):
    """Raised when a Phase move call violates the move-flag-precedence rule."""


def find_phase(plan: Plan, phase_id: str) -> Phase:
    """Return the Phase with canonical id ``phase_id`` or raise."""
    for phase in plan.phases:
        if phase.canonical_id == phase_id:
            return phase
    msg = f"Phase {phase_id!r} does not exist in this plan"
    raise PhaseNotFoundError(msg)


def edit_phase(
    plan: Plan,
    phase_id: str,
    *,
    title: str | None = None,
    intent: str | None = None,
) -> Phase:
    """Edit the Phase's title and / or intent paragraph."""
    phase = find_phase(plan, phase_id)
    if title is not None:
        phase.title = title
    if intent is not None:
        phase.intent = intent
    return phase


def move_phase(
    plan: Plan,
    phase_id: str,
    *,
    to_wave: str | None = None,
    before: str | None = None,
    after: str | None = None,
) -> Phase:
    """Re-parent and / or re-position a Phase.

    Mirrors :func:`step_ops.move_step` precedence:

    - ``--to-wave`` alone re-parents and appends.
    - ``--before`` / ``--after`` alone re-position within the current
      Wave; the anchor must share the moving Phase's parent.
    - Combining both re-parents AND positions; the anchor must reside
      in the destination Wave post-move.
    """
    if before is not None and after is not None:
        msg = "move_phase accepts at most one of --before / --after"
        raise MovePhaseError(msg)
    if to_wave is None and before is None and after is None:
        msg = "move_phase requires --to-wave, --before, or --after"
        raise MovePhaseError(msg)
    self_anchor = before == phase_id or after == phase_id
    if self_anchor:
        msg = (
            f"cannot move Phase {phase_id!r} relative to itself; "
            "anchor must be a different Phase"
        )
        raise MovePhaseError(msg)

    moving = find_phase(plan, phase_id)
    current_wave = _wave_of(plan, phase_id)
    dest_wave = (
        _resolve_wave_by_id(plan, to_wave) if to_wave is not None else current_wave
    )

    anchor_id = before if before is not None else after
    anchor_wave = _wave_of(plan, anchor_id) if anchor_id is not None else None
    if anchor_id is not None and dest_wave is not None and anchor_wave is not dest_wave:
        msg = (
            f"anchor Phase {anchor_id!r} is not in destination wave "
            f"{dest_wave.canonical_id!r}; cross-parent move requires the "
            "anchor to reside in the destination Wave"
        )
        raise MovePhaseError(msg)

    if current_wave is not None:
        current_wave.phases.remove(moving)
    plan.phases.remove(moving)

    if dest_wave is None:
        if anchor_id is None:
            plan.phases.append(moving)
        else:
            anchor_index = next(
                i
                for i, phase in enumerate(plan.phases)
                if phase.canonical_id == anchor_id
            )
            position = anchor_index if before is not None else anchor_index + 1
            plan.phases.insert(position, moving)
    else:
        if anchor_id is None:
            dest_wave.phases.append(moving)
        else:
            anchor_index = next(
                i
                for i, phase in enumerate(dest_wave.phases)
                if phase.canonical_id == anchor_id
            )
            position = anchor_index if before is not None else anchor_index + 1
            dest_wave.phases.insert(position, moving)
        # Rebuild plan.phases as the document-order union of all Wave phases.
        plan.phases.clear()
        for wave in plan.waves:
            plan.phases.extend(wave.phases)

    parent_wave_id = dest_wave.canonical_id if dest_wave is not None else None
    moving.display_path = phase_display_path(
        phase_id=moving.canonical_id,
        wave_id=parent_wave_id,
    )
    # Recompute child Step display paths.
    for step in moving.steps:
        step.display_path = _recompute_step_display_path(
            step_id=step.canonical_id,
            phase_id=moving.canonical_id,
            wave_id=parent_wave_id,
        )
    return moving


def remove_phase(plan: Plan, phase_id: str) -> tuple[str, list[str]]:
    """Remove a Phase and cascade-retire every descendant Step identifier.

    Per the CLI ADR's *Cascading retirement* rule, removing a parent
    container retires every descendant canonical identifier. The
    Step Records on disk are NOT deleted by this function; the
    convention surfaces them as orphans for ``vault check`` to flag.

    Args:
        plan: Parsed :class:`Plan`. Mutated in place.
        phase_id: Canonical id of the Phase to remove.

    Returns:
        A tuple of ``(retired_phase_id, retired_step_ids)``; the Step
        list is in document order.

    Raises:
        PhaseNotFoundError: When ``phase_id`` does not exist.
    """
    phase = find_phase(plan, phase_id)
    parent_wave = _wave_of(plan, phase_id)
    retired_step_ids = [step.canonical_id for step in phase.steps]

    for step in list(phase.steps):
        plan.steps.remove(step)
    plan.phases.remove(phase)
    if parent_wave is not None:
        parent_wave.phases.remove(phase)
    return phase.canonical_id, retired_step_ids


def _wave_of(plan: Plan, phase_id: str | None):
    """Return the Wave that owns ``phase_id`` or ``None`` for L2 plans."""
    if phase_id is None:
        return None
    for wave in plan.waves:
        for phase in wave.phases:
            if phase.canonical_id == phase_id:
                return wave
    return None


def _resolve_wave_by_id(plan: Plan, wave_id: str):
    """Return the Wave with canonical id ``wave_id`` or raise."""
    for wave in plan.waves:
        if wave.canonical_id == wave_id:
            return wave
    msg = f"wave {wave_id!r} does not exist in this plan"
    raise MovePhaseError(msg)


def _recompute_step_display_path(
    *, step_id: str, phase_id: str, wave_id: str | None
) -> str:
    """Recompute a Step display path; isolated to keep the import local."""
    from vaultspec_core.plan.display_path import step_display_path

    return step_display_path(step_id=step_id, phase_id=phase_id, wave_id=wave_id)


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
    if anchor_id is None:
        msg = "insert_phase received None anchor after exactly-one validation"
        raise AddPhaseError(msg)
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
