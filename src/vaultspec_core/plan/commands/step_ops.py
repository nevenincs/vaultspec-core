"""Step-level command handlers backing ``vaultspec-core vault plan step ...`` verbs.

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

from vaultspec_core.plan.commands._errors import PlanCommandError
from vaultspec_core.plan.display_path import step_display_path
from vaultspec_core.plan.frontmatter import Tier
from vaultspec_core.plan.identifiers import next_available_step
from vaultspec_core.plan.parser import Step

if TYPE_CHECKING:
    from vaultspec_core.plan.parser import Plan

__all__ = [
    "AddStepError",
    "AmbiguousStepError",
    "MoveStepError",
    "StepNotFoundError",
    "add_step",
    "check_step",
    "edit_step",
    "find_step",
    "insert_step",
    "move_step",
    "remove_step",
    "toggle_step",
    "uncheck_step",
]


class AddStepError(PlanCommandError, ValueError):
    """Raised when an add or insert call violates the parent-resolution rule."""


class StepNotFoundError(PlanCommandError, KeyError):
    """Raised when a Step canonical identifier does not exist in the plan."""


class AmbiguousStepError(PlanCommandError, ValueError):
    """Raised when a Step leaf identifier matches multiple live rows."""


class MoveStepError(PlanCommandError, ValueError):
    """Raised when a move call violates the move-flag-precedence rule.

    Per the CLI ADR's *Move-flag precedence* section, ``--before`` /
    ``--after`` require the anchor to share the moving Step's current
    parent Phase; cross-parent moves require ``--to-phase``. A
    combination ``--to-phase P## --before/--after S##`` is legal only
    when the anchor resides in the destination Phase post-move.
    """


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
    if anchor_id is None:
        msg = "insert_step received None anchor after exactly-one validation"
        raise AddStepError(msg)
    anchor_phase, anchor_index = _locate_step_in_phase(plan, anchor_id)
    anchor_step = find_step(plan, anchor_id)
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
        flat_index = plan.steps.index(anchor_step)
        position = flat_index if before is not None else flat_index + 1
        plan.steps.insert(position, new_step)
    else:
        position = anchor_index if before is not None else anchor_index + 1
        anchor_phase.steps.insert(position, new_step)
        flat_index = plan.steps.index(anchor_step)
        flat_position = flat_index if before is not None else flat_index + 1
        plan.steps.insert(flat_position, new_step)
    return new_step


# ---- State commands ---------------------------------------------------------


def find_step(plan: Plan, step_id: str) -> Step:
    """Return the Step matching ``step_id`` or raise.

    ``step_id`` may be a canonical leaf id (``S##``) or a full display
    path (``P##.S##`` / ``W##.P##.S##``). Display-path addressing lets
    repair commands target one row when a degraded plan temporarily
    contains duplicate Step ids.

    Raises:
        StepNotFoundError: When ``step_id`` is not present in the plan.
        AmbiguousStepError: When a leaf id matches multiple live rows.
    """
    matches = _matching_steps(plan, step_id)
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        display_paths = ", ".join(step.display_path for step in matches)
        msg = (
            f"Step {step_id!r} is ambiguous; use a full display path "
            f"to select one of: {display_paths}"
        )
        raise AmbiguousStepError(msg)
    msg = f"Step {step_id!r} does not exist in this plan"
    raise StepNotFoundError(msg)


def toggle_step(plan: Plan, step_id: str) -> Step:
    """Flip the Step's checkbox state. Non-idempotent by design."""
    step = find_step(plan, step_id)
    step.checked = not step.checked
    return step


def check_step(plan: Plan, step_id: str) -> Step:
    """Mark the Step closed. Idempotent: already-closed Steps are unchanged."""
    step = find_step(plan, step_id)
    step.checked = True
    return step


def uncheck_step(plan: Plan, step_id: str) -> Step:
    """Mark the Step open. Idempotent: already-open Steps are unchanged."""
    step = find_step(plan, step_id)
    step.checked = False
    return step


def edit_step(
    plan: Plan,
    step_id: str,
    *,
    action: str | None = None,
    scope: str | None = None,
) -> Step:
    """Edit the Step's action statement and / or scope clause.

    Args:
        plan: Parsed :class:`Plan`. Mutated in place.
        step_id: Canonical id of the Step to edit.
        action: New imperative-verb action; ``None`` leaves it unchanged.
        scope: New file or area scope; ``None`` leaves it unchanged.

    Raises:
        StepNotFoundError: When ``step_id`` is not present.
    """
    step = find_step(plan, step_id)
    if action is not None:
        step.action = action
    if scope is not None:
        step.scope = scope
    return step


# ---- Destructive ------------------------------------------------------------


def remove_step(plan: Plan, step_id: str) -> str:
    """Remove the Step with canonical id ``step_id``; identifier is retired.

    The convention's append-only / no-reuse rule guarantees the
    retired identifier is never re-allocated; the
    :func:`vaultspec_core.plan.identifiers.next_available_step` counter
    advances past it on subsequent allocations.

    Args:
        plan: Parsed :class:`Plan`. Mutated in place.
        step_id: Canonical id of the Step to remove.

    Returns:
        The retired canonical identifier.

    Raises:
        StepNotFoundError: When ``step_id`` does not exist.
    """
    step = find_step(plan, step_id)
    parent_phase = _phase_of_step(plan, step)
    if parent_phase is not None:
        parent_phase.steps.remove(step)
    plan.steps.remove(step)
    if not any(other.canonical_id == step.canonical_id for other in plan.steps):
        plan.retired_step_ids.add(step.canonical_id)
    return step.canonical_id


# ---- Re-parenting / re-positioning ------------------------------------------


def move_step(
    plan: Plan,
    step_id: str,
    *,
    to_phase: str | None = None,
    before: str | None = None,
    after: str | None = None,
) -> Step:
    """Re-parent and / or re-position a Step.

    Behaviour per the CLI ADR's *Move-flag precedence* rule:

    - ``--to-phase`` alone re-parents the Step to the named Phase and
      appends it at the tail of the new parent.
    - ``--before`` / ``--after`` alone re-position within the current
      parent; the anchor must share the moving Step's parent Phase.
    - ``--to-phase`` plus ``--before`` / ``--after`` re-parents AND
      positions; the anchor must reside in the destination Phase
      post-move.

    Args:
        plan: Parsed :class:`Plan`. Mutated in place.
        step_id: Canonical id of the Step to move.
        to_phase: Destination Phase canonical id.
        before: Anchor Step id the moved row should precede.
        after: Anchor Step id the moved row should follow.

    Returns:
        The moved :class:`Step` with its display path recomputed.

    Raises:
        StepNotFoundError: When ``step_id`` does not exist.
        MoveStepError: When the flag combination violates precedence.
    """
    if before is not None and after is not None:
        msg = "move_step accepts at most one of --before / --after"
        raise MoveStepError(msg)
    if to_phase is None and before is None and after is None:
        msg = "move_step requires --to-phase, --before, or --after"
        raise MoveStepError(msg)
    if before == step_id or after == step_id:
        msg = (
            f"cannot move Step {step_id!r} relative to itself; "
            "anchor must be a different Step"
        )
        raise MoveStepError(msg)

    moving = find_step(plan, step_id)
    current_phase = _phase_of_step(plan, moving)

    # Determine destination Phase.
    if to_phase is not None:
        dest_phase = _resolve_phase_by_id(plan, to_phase)
    else:
        dest_phase = current_phase

    # Anchor checks.
    anchor_id = before if before is not None else after
    anchor_phase = _phase_of(plan, anchor_id) if anchor_id is not None else None
    if (
        anchor_id is not None
        and dest_phase is not None
        and anchor_phase is not dest_phase
    ):
        msg = (
            f"anchor Step {anchor_id!r} is not in destination phase "
            f"{dest_phase.canonical_id!r}; cross-parent move requires "
            "the anchor to reside in the destination Phase"
        )
        raise MoveStepError(msg)

    # Detach from current parent.
    if current_phase is not None:
        current_phase.steps.remove(moving)

    # Compute insertion index.
    if dest_phase is None:
        # L1 plan: re-position within plan.steps.
        plan.steps.remove(moving)
        if anchor_id is None:
            plan.steps.append(moving)
        else:
            anchor = find_step(plan, anchor_id)
            anchor_index = plan.steps.index(anchor)
            position = anchor_index if before is not None else anchor_index + 1
            plan.steps.insert(position, moving)
    else:
        if anchor_id is None:
            dest_phase.steps.append(moving)
        else:
            anchor = find_step(plan, anchor_id)
            anchor_index = dest_phase.steps.index(anchor)
            position = anchor_index if before is not None else anchor_index + 1
            dest_phase.steps.insert(position, moving)
        # Refresh the flat plan.steps mirror to keep document order coherent.
        plan.steps.remove(moving)
        # Re-insert at the position matching the destination phase row order.
        flat_index = _compute_flat_position(plan, moving)
        plan.steps.insert(flat_index, moving)

    # Recompute display path against new ancestor chain.
    wave_id = _wave_id_of(plan, dest_phase) if dest_phase is not None else None
    parent_id = dest_phase.canonical_id if dest_phase is not None else None
    moving.display_path = step_display_path(
        step_id=moving.canonical_id,
        phase_id=parent_id,
        wave_id=wave_id,
    )
    return moving


# ---- Internals --------------------------------------------------------------


def _phase_of(plan: Plan, step_id: str | None):
    """Return the Phase that owns ``step_id`` or ``None`` for L1 plans."""
    if step_id is None:
        return None
    return _phase_of_step(plan, find_step(plan, step_id))


def _phase_of_step(plan: Plan, target: Step):
    """Return the Phase that owns ``target`` or ``None`` for L1 plans."""
    if plan.frontmatter.tier is Tier.L1:
        return None
    for phase in plan.phases:
        for step in phase.steps:
            if step is target:
                return phase
    return None


def _resolve_phase_by_id(plan: Plan, phase_id: str):
    """Return the Phase with canonical id ``phase_id`` or raise."""
    for phase in plan.phases:
        if phase.canonical_id == phase_id:
            return phase
    msg = f"phase {phase_id!r} does not exist in this plan"
    raise MoveStepError(msg)


def _compute_flat_position(plan: Plan, moving: Step) -> int:
    """Return the index in ``plan.steps`` matching the moving Step's new spot.

    The flat ``plan.steps`` mirrors the document-order union of every
    Phase's ``steps`` list. After re-attaching to ``dest_phase``, this
    helper finds the position the Phase's index implies. The moving Step
    must be present in some Phase's ``steps`` list before this function
    is called; the loop falls through only when that invariant is
    violated and surfaces the bug rather than masking it.
    """
    flat_position = 0
    for phase in plan.phases:
        for step in phase.steps:
            if step is moving:
                return flat_position
            flat_position += 1
    msg = (
        f"flat-mirror invariant violated: moving Step "
        f"{moving.canonical_id!r} not present in any Phase after "
        "re-attach. This indicates a bug in the move handler chain."
    )
    raise RuntimeError(msg)


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
    anchor = find_step(plan, anchor_id)
    if plan.frontmatter.tier is Tier.L1:
        return None, 0
    for phase in plan.phases:
        for index, step in enumerate(phase.steps):
            if step is anchor:
                return phase, index
    msg = f"anchor Step {anchor_id!r} does not exist in this plan"
    raise AddStepError(msg)


def _matching_steps(plan: Plan, step_id: str) -> list[Step]:
    """Return live Steps matching a leaf id or full display path."""
    if "." in step_id:
        return [step for step in plan.steps if step.display_path == step_id]
    return [step for step in plan.steps if step.canonical_id == step_id]


def _wave_id_of(plan: Plan, phase) -> str | None:
    """Return the Wave canonical id that owns ``phase``, or ``None`` at L2."""
    if plan.frontmatter.tier is Tier.L2:
        return None
    for wave in plan.waves:
        if any(p.canonical_id == phase.canonical_id for p in wave.phases):
            return wave.canonical_id
    return None
