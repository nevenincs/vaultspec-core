"""Step-level command handlers backing ``vault plan step ...`` verbs.

Implements:

- ``add`` (W02.P03.S59): append a new Step at the next-available
  ``S##`` to the tail of the target Phase or document.
- ``insert`` (W02.P03.S60): place a new Step at a named document
  position (``--before S##`` / ``--after S##``); canonical identifier
  is next-available; parent is inferred from the anchor.

State / re-parenting / destructive verbs follow in W02.P04 and
W02.P05.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vaultspec_core.plan.display_path import step_display_path
from vaultspec_core.plan.frontmatter import Tier
from vaultspec_core.plan.identifiers import next_available_step
from vaultspec_core.plan.parser import Step

if TYPE_CHECKING:
    from vaultspec_core.plan.parser import Plan

__all__ = ["AddStepError", "add_step", "insert_step"]


class AddStepError(ValueError):
    """Raised when an add or insert call violates the parent-resolution rule."""


def add_step(
    plan: Plan,
    *,
    action: str,
    scope: str,
    phase_id: str | None = None,
) -> Step:
    """Append a Step at the next-available ``S##`` to the tail of its parent.

    Args:
        plan: Parsed :class:`Plan` model. Mutated in place: the new
            Step is appended to ``plan.steps`` and to the target
            container's ``steps`` list.
        action: Imperative-verb action statement.
        scope: File or area scope (no surrounding backticks).
        phase_id: Required at ``L2``/``L3``/``L4``; ignored at ``L1``.

    Returns:
        The newly-created :class:`Step`.

    Raises:
        AddStepError: When the parent-resolution rule is violated
            (``phase_id`` required but missing at L2+, or ``phase_id``
            does not exist in the plan).
    """
    target_phase = _resolve_phase_for_add(plan, phase_id=phase_id)
    canonical_id = next_available_step(plan)

    wave_id = _wave_id_of(plan, target_phase) if target_phase is not None else None
    parent_id = target_phase.canonical_id if target_phase is not None else None
    new_step = Step(
        canonical_id=canonical_id,
        display_path=step_display_path(
            step_id=canonical_id,
            phase_id=parent_id,
            wave_id=wave_id,
        ),
        checked=False,
        action=action,
        scope=scope,
        raw_line="",
        line_number=0,
    )

    plan.steps.append(new_step)
    if target_phase is not None:
        target_phase.steps.append(new_step)
    return new_step


def insert_step(
    plan: Plan,
    *,
    action: str,
    scope: str,
    before: str | None = None,
    after: str | None = None,
) -> Step:
    """Place a Step at a named document position; parent inferred from anchor.

    Exactly one of ``before`` or ``after`` must be supplied. The
    anchor's canonical Step identifier (``S##``) names the existing
    Step that the new row sits next to in document order. The new
    Step inherits the anchor's parent Phase / Wave; cross-parent
    inserts are not supported here (use ``step move`` after).

    Args:
        plan: Parsed :class:`Plan` model. Mutated in place.
        action: Imperative-verb action statement.
        scope: File or area scope.
        before: Anchor Step identifier (``S##``) the new row precedes.
        after: Anchor Step identifier the new row follows.

    Returns:
        The newly-created :class:`Step`.

    Raises:
        AddStepError: When neither or both of ``before`` / ``after``
            are supplied, or the anchor identifier is not in ``plan``.
    """
    if before is None and after is None:
        msg = "insert_step requires either --before or --after"
        raise AddStepError(msg)
    if before is not None and after is not None:
        msg = "insert_step accepts at most one of --before / --after"
        raise AddStepError(msg)

    anchor_id = before if before is not None else after
    assert anchor_id is not None  # exactly-one check above ensures this
    anchor_phase, anchor_index = _locate_step_in_phase(plan, anchor_id)
    canonical_id = next_available_step(plan)
    wave_id = _wave_id_of(plan, anchor_phase) if anchor_phase is not None else None
    parent_id = anchor_phase.canonical_id if anchor_phase is not None else None
    new_step = Step(
        canonical_id=canonical_id,
        display_path=step_display_path(
            step_id=canonical_id,
            phase_id=parent_id,
            wave_id=wave_id,
        ),
        checked=False,
        action=action,
        scope=scope,
        raw_line="",
        line_number=0,
    )

    if anchor_phase is None:
        # L1 plan: insert into the flat plan.steps list.
        flat_index = next(
            i for i, step in enumerate(plan.steps) if step.canonical_id == anchor_id
        )
        position = flat_index if before is not None else flat_index + 1
        plan.steps.insert(position, new_step)
    else:
        position = anchor_index if before is not None else anchor_index + 1
        anchor_phase.steps.insert(position, new_step)
        flat_index = next(
            i for i, step in enumerate(plan.steps) if step.canonical_id == anchor_id
        )
        flat_position = flat_index if before is not None else flat_index + 1
        plan.steps.insert(flat_position, new_step)
    return new_step


# ---- Internals --------------------------------------------------------------


def _resolve_phase_for_add(plan: Plan, *, phase_id: str | None):
    """Return the target Phase or ``None`` for L1 plans.

    Raises:
        AddStepError: When parent resolution fails.
    """
    tier = plan.frontmatter.tier
    if tier is Tier.L1:
        if phase_id is not None:
            msg = "L1 plans do not have Phases; --phase must not be set"
            raise AddStepError(msg)
        return None
    if phase_id is None:
        msg = (
            f"{tier.value} plans require --phase P##; the parent Phase "
            "cannot be inferred without an anchor."
        )
        raise AddStepError(msg)
    for phase in plan.phases:
        if phase.canonical_id == phase_id:
            return phase
    msg = f"phase {phase_id!r} does not exist in this plan"
    raise AddStepError(msg)


def _locate_step_in_phase(plan: Plan, anchor_id: str):
    """Find the Phase that owns ``anchor_id`` and the Step's index within it.

    For L1 plans the Phase is ``None`` and the index is irrelevant.

    Raises:
        AddStepError: When the anchor is not present in the plan.
    """
    if plan.frontmatter.tier is Tier.L1:
        for step in plan.steps:
            if step.canonical_id == anchor_id:
                return None, 0
        msg = f"anchor Step {anchor_id!r} does not exist in this plan"
        raise AddStepError(msg)
    for phase in plan.phases:
        for index, step in enumerate(phase.steps):
            if step.canonical_id == anchor_id:
                return phase, index
    msg = f"anchor Step {anchor_id!r} does not exist in this plan"
    raise AddStepError(msg)


def _wave_id_of(plan: Plan, phase) -> str | None:
    """Return the Wave canonical id that owns ``phase``, or ``None`` at L2."""
    if plan.frontmatter.tier is Tier.L2:
        return None
    for wave in plan.waves:
        if any(p.canonical_id == phase.canonical_id for p in wave.phases):
            return wave.canonical_id
    return None
