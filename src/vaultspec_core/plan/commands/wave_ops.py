"""Wave-level add and insert commands.

Implements:

- ``add`` (W02.P03.S63): append a Wave at the next-available ``W##``.
- ``insert`` (W02.P03.S64): place a Wave at a named document
  position (``--before W##`` / ``--after W##``); canonical
  identifier is next-available; the Epic frame is implicit at ``L4``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vaultspec_core.plan.frontmatter import Tier
from vaultspec_core.plan.identifiers import next_available_wave
from vaultspec_core.plan.parser import Wave

if TYPE_CHECKING:
    from vaultspec_core.plan.parser import Plan

__all__ = [
    "AddWaveError",
    "MoveWaveError",
    "WaveNotFoundError",
    "add_wave",
    "edit_wave",
    "find_wave",
    "insert_wave",
    "move_wave",
    "remove_wave",
]


class AddWaveError(ValueError):
    """Raised when a Wave add or insert call violates tier rules."""


def add_wave(plan: Plan, *, title: str, intent: str) -> Wave:
    """Append a Wave at the next-available ``W##`` to the document tail.

    Raises:
        AddWaveError: When the plan tier does not support Waves
            (only ``L3`` and ``L4`` do).
    """
    _require_wave_supporting_tier(plan)
    canonical_id = next_available_wave(plan)
    new_wave = Wave(
        canonical_id=canonical_id,
        title=title,
        intent=intent,
        line_number=0,
    )
    plan.waves.append(new_wave)
    return new_wave


def insert_wave(
    plan: Plan,
    *,
    title: str,
    intent: str,
    before: str | None = None,
    after: str | None = None,
) -> Wave:
    """Place a Wave at a named document position relative to an anchor."""
    _require_wave_supporting_tier(plan)
    if before is None and after is None:
        msg = "insert_wave requires either --before or --after"
        raise AddWaveError(msg)
    if before is not None and after is not None:
        msg = "insert_wave accepts at most one of --before / --after"
        raise AddWaveError(msg)

    anchor_id = before if before is not None else after
    if anchor_id is None:
        msg = "insert_wave received None anchor after exactly-one validation"
        raise AddWaveError(msg)

    anchor_index = next(
        (i for i, wave in enumerate(plan.waves) if wave.canonical_id == anchor_id),
        -1,
    )
    if anchor_index < 0:
        msg = f"anchor Wave {anchor_id!r} does not exist in this plan"
        raise AddWaveError(msg)

    canonical_id = next_available_wave(plan)
    new_wave = Wave(
        canonical_id=canonical_id,
        title=title,
        intent=intent,
        line_number=0,
    )
    position = anchor_index if before is not None else anchor_index + 1
    plan.waves.insert(position, new_wave)
    return new_wave


class WaveNotFoundError(KeyError):
    """Raised when a Wave canonical identifier does not exist in the plan."""


class MoveWaveError(ValueError):
    """Raised when a Wave move call references a non-existent anchor."""


def find_wave(plan: Plan, wave_id: str) -> Wave:
    """Return the Wave with canonical id ``wave_id`` or raise."""
    for wave in plan.waves:
        if wave.canonical_id == wave_id:
            return wave
    msg = f"Wave {wave_id!r} does not exist in this plan"
    raise WaveNotFoundError(msg)


def edit_wave(
    plan: Plan,
    wave_id: str,
    *,
    title: str | None = None,
    intent: str | None = None,
) -> Wave:
    """Edit the Wave's title and / or intent paragraph."""
    wave = find_wave(plan, wave_id)
    if title is not None:
        wave.title = title
    if intent is not None:
        wave.intent = intent
    return wave


def move_wave(
    plan: Plan,
    wave_id: str,
    *,
    before: str | None = None,
    after: str | None = None,
) -> Wave:
    """Re-position a Wave in document order.

    Wave move accepts only ``--before`` / ``--after`` because the
    Epic frame is implicit; there is no ``--to-epic``. Descendant
    Phase and Step display paths are recomputed against the new
    position.
    """
    if before is None and after is None:
        msg = "move_wave requires either --before or --after"
        raise MoveWaveError(msg)
    if before is not None and after is not None:
        msg = "move_wave accepts at most one of --before / --after"
        raise MoveWaveError(msg)

    anchor_id = before if before is not None else after
    if anchor_id is None:
        msg = "move_wave received None anchor after exactly-one validation"
        raise MoveWaveError(msg)
    if anchor_id == wave_id:
        msg = (
            f"cannot move Wave {wave_id!r} relative to itself; "
            "anchor must be a different Wave"
        )
        raise MoveWaveError(msg)

    moving = find_wave(plan, wave_id)
    if not any(wave.canonical_id == anchor_id for wave in plan.waves):
        msg = f"anchor Wave {anchor_id!r} does not exist in this plan"
        raise MoveWaveError(msg)

    plan.waves.remove(moving)
    new_anchor_index = next(
        i for i, wave in enumerate(plan.waves) if wave.canonical_id == anchor_id
    )
    position = new_anchor_index if before is not None else new_anchor_index + 1
    plan.waves.insert(position, moving)

    # Rebuild plan.phases / plan.steps as the document-order union.
    # The mirrors are mutated in place via clear() + append: external
    # holders of the list reference observe the rebuild, but holders of
    # individual Phase / Step objects (the canonical references) are
    # unaffected. Callers that need a stable list snapshot must copy
    # via list(plan.steps) before calling move_wave.
    plan.phases.clear()
    plan.steps.clear()
    for wave in plan.waves:
        for phase in wave.phases:
            plan.phases.append(phase)
            for step in phase.steps:
                plan.steps.append(step)

    # Recompute descendant display paths (Wave id has not changed but
    # Phase / Step paths embed it explicitly).
    from vaultspec_core.plan.display_path import (
        phase_display_path,
        step_display_path,
    )

    for phase in moving.phases:
        phase.display_path = phase_display_path(
            phase_id=phase.canonical_id,
            wave_id=moving.canonical_id,
        )
        for step in phase.steps:
            step.display_path = step_display_path(
                step_id=step.canonical_id,
                phase_id=phase.canonical_id,
                wave_id=moving.canonical_id,
            )
    return moving


def remove_wave(plan: Plan, wave_id: str) -> tuple[str, list[str], list[str]]:
    """Remove a Wave and cascade-retire every descendant Phase and Step id.

    Returns:
        ``(retired_wave_id, retired_phase_ids, retired_step_ids)``.

    Raises:
        WaveNotFoundError: When ``wave_id`` does not exist.
    """
    wave = find_wave(plan, wave_id)
    retired_phase_ids = [phase.canonical_id for phase in wave.phases]
    retired_step_ids = [
        step.canonical_id for phase in wave.phases for step in phase.steps
    ]

    for phase in list(wave.phases):
        for step in list(phase.steps):
            plan.steps.remove(step)
        plan.phases.remove(phase)
    plan.waves.remove(wave)
    plan.retired_wave_ids.add(wave.canonical_id)
    plan.retired_phase_ids.update(retired_phase_ids)
    plan.retired_step_ids.update(retired_step_ids)
    return wave.canonical_id, retired_phase_ids, retired_step_ids


def _require_wave_supporting_tier(plan: Plan) -> None:
    """Raise :class:`AddWaveError` when the plan tier rejects Waves."""
    if plan.frontmatter.tier in (Tier.L1, Tier.L2):
        msg = (
            f"{plan.frontmatter.tier.value} plans do not support Wave "
            "headings; promote to L3 or L4 first."
        )
        raise AddWaveError(msg)
