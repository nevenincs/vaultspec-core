"""Integrity guards for serialised plan writes, shared by every write path.

Two defensive checks protect a plan document at the moment its mutated,
re-serialised text is about to replace the on-disk bytes, and they must run on
*every* write path so no surface can corrupt a plan the others protect:

- **Unexpected-retirement guard** (issue #150): a legitimate mutation retires
  only the canonical identifiers the operation intends to retire. Any identifier
  that becomes retired beyond that expected set signals a serialisation conflict
  that would silently drop live plan items, so the write is refused. This is the
  guard that protects canonical-identifier and gap-no-reuse integrity, so it is
  shared rather than owned by the CLI alone.
- **Growth-ceiling guard** (issue #125): a single structural edit never
  multiplies a plan several times over, so serialised output larger than
  ``max(floor, factor * len(source))`` signals a serialiser fault and the write
  is refused rather than corrupting the file or exhausting the disk.

Both the CLI plan-mutation verbs and the MCP ``plan_edit`` / ``plan_progress``
tools serialise a mutated plan and write it back; routing both through
:func:`guard_plan_write` guarantees the MCP surface inherits exactly the
integrity the CLI enforces, with no second copy of the check to drift.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vaultspec_core.plan.commands._errors import PlanCommandError

if TYPE_CHECKING:
    from vaultspec_core.plan.parser import Plan

__all__ = [
    "PlanWriteGuardError",
    "guard_plan_write",
]

#: Byte floor below which the growth ceiling never trips, so tiny plans stay
#: editable even when a single edit more than quadruples their size.
_PLAN_GROWTH_FLOOR = 65_536

#: Multiplier applied to the source length to derive the growth ceiling.
_PLAN_GROWTH_FACTOR = 4


class PlanWriteGuardError(PlanCommandError):
    """A serialised plan write was refused by an integrity guard.

    Subclasses :class:`~vaultspec_core.plan.commands._errors.PlanCommandError`
    so the CLI's ``_render_user_errors`` decorator renders it as a one-line
    error exactly as before the extraction, while the MCP tool handlers surface
    it as a protocol ``isError`` result like any other whole-call failure.
    """


def _retired_ids(plan: Plan) -> set[str]:
    """Return the union of a plan's retired step, phase, and wave identifiers."""
    return plan.retired_step_ids | plan.retired_phase_ids | plan.retired_wave_ids


def guard_plan_write(
    original_text: str,
    new_text: str,
    expected_retired: set[str] | None,
    *,
    path_name: str,
) -> None:
    """Run both plan-write integrity guards over a pending serialisation.

    Parses the pre- and post-mutation text once, then enforces the
    unexpected-retirement and growth-ceiling guards in that order. A parse
    failure on either text is itself a refusal, since an unparseable result is
    never a safe thing to persist.

    Args:
        original_text: The plan document's pre-mutation text.
        new_text: The serialised, stamp-refreshed text about to be written.
        expected_retired: The canonical identifiers the mutation legitimately
            retires (empty or ``None`` for a mutation that retires nothing).
        path_name: The plan filename, used only in the growth-ceiling message.

    Raises:
        PlanWriteGuardError: When the mutated text fails to parse, retires an
            identifier outside *expected_retired*, or exceeds the growth ceiling.
    """
    from vaultspec_core.plan.parser import parse_plan

    try:
        old_plan = parse_plan(original_text)
        new_plan = parse_plan(new_text)
    except Exception as exc:  # any parse failure is itself a refusal
        msg = f"Plan validation failed during parsing: {exc}"
        raise PlanWriteGuardError(msg) from exc

    newly_retired = _retired_ids(new_plan) - _retired_ids(old_plan)
    expected = expected_retired if expected_retired is not None else set()
    unexpected = newly_retired - expected
    if unexpected:
        joined = ", ".join(sorted(unexpected))
        msg = (
            f"mutation aborted: unexpected retirement of active plan items: "
            f"{joined}. This indicates a serialization conflict."
        )
        raise PlanWriteGuardError(msg)

    growth_ceiling = max(_PLAN_GROWTH_FLOOR, _PLAN_GROWTH_FACTOR * len(original_text))
    if len(new_text) > growth_ceiling:
        msg = (
            f"refusing to write {path_name}: serialised output "
            f"({len(new_text)} bytes) is implausibly larger than the source "
            f"({len(original_text)} bytes); this indicates a serialiser fault, "
            "not an intended edit. The file on disk was left unchanged."
        )
        raise PlanWriteGuardError(msg)
