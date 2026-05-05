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

__all__ = ["AddWaveError", "add_wave", "insert_wave"]


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
    assert anchor_id is not None

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


def _require_wave_supporting_tier(plan: Plan) -> None:
    """Raise :class:`AddWaveError` when the plan tier rejects Waves."""
    if plan.frontmatter.tier in (Tier.L1, Tier.L2):
        msg = (
            f"{plan.frontmatter.tier.value} plans do not support Wave "
            "headings; promote to L3 or L4 first."
        )
        raise AddWaveError(msg)
