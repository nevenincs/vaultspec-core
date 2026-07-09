"""Plan-domain MCP tools: ``plan_progress`` and ``plan_edit``.

Both tools are thin wrappers over the plan step-ops core
(:mod:`vaultspec_core.plan.commands.step_ops`) plus the parser and
serialiser - no plan-structure logic is authored in this layer, so canonical
identifiers and the gap-no-reuse rule are guaranteed by the owning verb logic
and by nothing here. ``plan_progress`` marks a batch of steps ``checked`` or
``unchecked`` (explicit states only, so it is idempotent); ``plan_edit``
carries the ``add`` / ``insert`` / ``edit`` / ``remove`` step-authoring
operations. Both address a plan by feature or stem through the shared
:func:`~vaultspec_core.mcp_server.plan_resolver.resolve_plan`, and both write
through the serialiser with a refreshed ``modified:`` stamp exactly as the
CLI verbs do.
"""

from __future__ import annotations

import datetime
import logging
from typing import TYPE_CHECKING, Any

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations
from pydantic import BaseModel

from ...core.types import get_context as _get_ctx
from ..isolation import isolated_context as _isolated_context

if TYPE_CHECKING:
    from pathlib import Path

    from mcp.server.fastmcp import FastMCP

    from ...plan.parser import Plan

logger = logging.getLogger(__name__)

__all__ = ["register_plan_tools"]


# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------


class StepStateChange(BaseModel):
    """One step-state change in a batch ``plan_progress`` call.

    Attributes:
        step_id: The step's canonical identifier (``S##``) or full display
            path (``P##.S##`` / ``W##.P##.S##``) to disambiguate a degraded
            plan.
        state: The target state - ``checked`` (closed) or ``unchecked``
            (open). Toggle is deliberately excluded so the tool is
            idempotent.
    """

    step_id: str
    state: str


class PlanEditOperation(BaseModel):
    """One step-authoring operation in a batch ``plan_edit`` call.

    Attributes:
        operation: The verb - ``add`` (append a step to a phase or the
            document tail), ``insert`` (place a step before/after an anchor),
            ``edit`` (change a step's action and/or scope), or ``remove``
            (retire a step).
        action: The imperative-verb action statement (required for ``add`` /
            ``insert``; optional for ``edit``).
        scope: The file or area scope clause (required for ``add`` /
            ``insert``; optional for ``edit``).
        phase_id: The parent phase (``P##``) for ``add`` at tier L2+.
        before: The anchor step (``S##``) the inserted step precedes.
        after: The anchor step (``S##``) the inserted step follows.
        step_id: The target step (``S##``) for ``edit`` / ``remove``.
    """

    operation: str
    action: str | None = None
    scope: str | None = None
    phase_id: str | None = None
    before: str | None = None
    after: str | None = None
    step_id: str | None = None


# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------


class StepChangeResult(BaseModel):
    """The outcome of one ``plan_progress`` state change.

    Attributes:
        step_id: The submitted step address, echoed back.
        state: The requested target state.
        status: ``updated`` when the checkbox changed, ``unchanged`` when it
            already held the target state, ``failed`` when the step could not
            be resolved.
        error: The structured failure payload on ``failed``, else ``None``.
    """

    step_id: str
    state: str
    status: str
    error: dict[str, Any] | None = None


class PlanProgressResult(BaseModel):
    """The whole-call result of a ``plan_progress`` invocation.

    Attributes:
        status: The aggregate outcome - ``ok`` / ``mixed`` / ``failed``.
        plan: The resolved plan stem.
        items: The per-step change results in submission order.
        total_steps: The plan's total step count after the batch.
        steps_completed: The checked-step count after the batch.
        completion_percent: The completion percent after the batch.
        next_open_step: The display path of the first open step, or ``None``.
    """

    status: str
    plan: str
    items: list[StepChangeResult]
    total_steps: int
    steps_completed: int
    completion_percent: float
    next_open_step: str | None


class PlanEditItemResult(BaseModel):
    """The outcome of one ``plan_edit`` operation.

    Attributes:
        operation: The submitted verb, echoed back.
        status: ``created`` (add/insert), ``updated`` (edit), ``removed``
            (remove), or ``failed``.
        step_id: The canonical identifier created, edited, or retired, or
            ``None`` on failure.
        error: The structured failure payload on ``failed``, else ``None``.
    """

    operation: str
    status: str
    step_id: str | None = None
    error: dict[str, Any] | None = None


class PlanEditResult(BaseModel):
    """The whole-call result of a ``plan_edit`` invocation.

    Attributes:
        status: The aggregate outcome - ``ok`` / ``mixed`` / ``failed``.
        plan: The resolved plan stem.
        items: The per-operation results in submission order.
        total_steps: The plan's total step count after the batch.
        steps_completed: The checked-step count after the batch.
        next_open_step: The display path of the first open step, or ``None``.
    """

    status: str
    plan: str
    items: list[PlanEditItemResult]
    total_steps: int
    steps_completed: int
    next_open_step: str | None


# ---------------------------------------------------------------------------
# Shared plan load / mutate / save
# ---------------------------------------------------------------------------


def _load_plan(path: Path) -> tuple[Plan, str]:
    """Parse the plan document at *path*, returning the plan and its text.

    Args:
        path: The plan document path.

    Returns:
        A two-tuple ``(parsed_plan, original_text)``.
    """
    from ...plan.parser import parse_plan

    original_text = path.read_text(encoding="utf-8")
    return parse_plan(original_text), original_text


def _save_plan(
    path: Path,
    plan: Plan,
    original_text: str,
    expected_retired: set[str] | None = None,
) -> bool:
    """Serialise *plan* and write it back through the owning serialiser.

    Mirrors the CLI plan-mutation write path: the plan is serialised with
    unknown blocks preserved, its ``modified:`` stamp is refreshed to today,
    the shared integrity guards run over the pending text, and the file is
    written atomically only when the bytes actually changed (so an all-no-op
    batch never bumps the stamp). Routing through
    :func:`~vaultspec_core.plan.write_guard.guard_plan_write` gives the MCP
    surface the same unexpected-retirement and growth-ceiling protection the
    CLI enforces, so a serialisation conflict that would silently drop a live
    step surfaces as a whole-call ``isError`` rather than a corrupt write.

    Args:
        path: The plan document path.
        plan: The mutated :class:`Plan` to serialise.
        original_text: The document's pre-mutation text.
        expected_retired: Canonical identifiers the batch legitimately retired
            (the ``remove`` operations' targets), or ``None`` for a mutation
            that retires nothing.

    Returns:
        ``True`` when the file was rewritten, ``False`` on a no-op.

    Raises:
        PlanWriteGuardError: When the pending text retires an identifier
            outside *expected_retired* or exceeds the growth ceiling.
    """
    from ...core.helpers import atomic_write
    from ...plan.serialiser import serialise_plan
    from ...plan.write_guard import guard_plan_write
    from ...vaultcore import refresh_modified_stamp

    new_text = serialise_plan(plan, canonicalise=False)
    new_text = refresh_modified_stamp(new_text, datetime.date.today())
    guard_plan_write(original_text, new_text, expected_retired, path_name=path.name)
    if new_text == original_text:
        return False
    atomic_write(path, new_text)
    return True


def _progress_summary(plan: Plan) -> tuple[int, int, float, str | None]:
    """Return ``(total, completed, percent, next_open_step)`` for *plan*."""
    from ...plan.status import collect_status

    status = collect_status(plan)
    return (
        status.step_count,
        status.steps_completed,
        status.completion_percent,
        status.next_open_step,
    )


def _reduce(statuses: list[str], success: set[str]) -> str:
    """Fold per-item statuses into ``ok`` / ``mixed`` / ``failed``."""
    if not statuses:
        return "ok"
    good = sum(1 for s in statuses if s in success)
    if good == len(statuses):
        return "ok"
    if good == 0:
        return "failed"
    return "mixed"


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_plan_tools(mcp: FastMCP) -> None:
    """Register the ``plan_progress`` and ``plan_edit`` plan tools on *mcp*.

    ``plan_progress`` is idempotent (explicit ``checked`` / ``unchecked``
    states only, no toggle). ``plan_edit`` is non-idempotent and
    destructive-annotated (``remove`` retires a step). Both declare
    structured output through their typed return models and route every
    mutation through the plan step-ops core.

    Args:
        mcp: The :class:`~mcp.server.fastmcp.FastMCP` instance to decorate.
    """

    @mcp.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    @_isolated_context
    async def plan_progress(
        ctx: Context,
        plan: str,
        steps: list[StepStateChange],
    ) -> PlanProgressResult:
        """Mark plan steps closed or open by canonical identifier.

        Resolves the plan by feature tag or stem, then applies each explicit
        ``checked`` / ``unchecked`` state through the plan step-ops core. A
        step already in the requested state is a successful ``unchanged``; an
        unresolvable step id is a per-item ``failed``. The plan is written
        once at the end (only when a state actually changed), and the
        updated completion counts and next open step are returned.

        Args:
            ctx: The MCP request context.
            plan: A feature tag or plan stem/path addressing one plan.
            steps: The batch of step-state changes.

        Returns:
            The :class:`PlanProgressResult` with per-step outcomes and the
            post-batch completion facts.

        Raises:
            ValueError: When ``steps`` is empty, a state is invalid, or the
                plan address does not resolve to a unique plan.
        """
        from ...plan.commands.step_ops import (
            AmbiguousStepError,
            StepNotFoundError,
            check_step,
            find_step,
            uncheck_step,
        )
        from ..plan_resolver import PlanResolutionError, resolve_plan

        if not steps:
            raise ValueError("plan_progress requires at least one step change")

        root_dir = _get_ctx().target_dir
        try:
            resolved = resolve_plan(root_dir, plan)
        except PlanResolutionError as exc:
            raise ValueError(str(exc)) from exc

        await ctx.info(f"plan_progress: {resolved.stem} {len(steps)} change(s)")

        parsed, original_text = _load_plan(resolved.path)
        items: list[StepChangeResult] = []
        changed = False

        for change in steps:
            if change.state not in ("checked", "unchecked"):
                items.append(
                    StepChangeResult(
                        step_id=change.step_id,
                        state=change.state,
                        status="failed",
                        error={
                            "message": (
                                f"Invalid state {change.state!r}; use 'checked' "
                                "or 'unchecked'."
                            )
                        },
                    )
                )
                continue
            want_checked = change.state == "checked"
            try:
                step = find_step(parsed, change.step_id)
            except (StepNotFoundError, AmbiguousStepError) as exc:
                items.append(
                    StepChangeResult(
                        step_id=change.step_id,
                        state=change.state,
                        status="failed",
                        error={"message": str(exc)},
                    )
                )
                continue
            already = step.checked == want_checked
            (check_step if want_checked else uncheck_step)(parsed, change.step_id)
            if not already:
                changed = True
            items.append(
                StepChangeResult(
                    step_id=change.step_id,
                    state=change.state,
                    status="unchanged" if already else "updated",
                )
            )

        if changed:
            _save_plan(resolved.path, parsed, original_text)

        total, completed, percent, next_open = _progress_summary(parsed)
        return PlanProgressResult(
            status=_reduce([i.status for i in items], {"updated", "unchanged"}),
            plan=resolved.stem,
            items=items,
            total_steps=total,
            steps_completed=completed,
            completion_percent=percent,
            next_open_step=next_open,
        )

    @mcp.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    @_isolated_context
    async def plan_edit(
        ctx: Context,
        plan: str,
        operations: list[PlanEditOperation],
    ) -> PlanEditResult:
        """Author plan steps: add, insert, edit, or remove.

        Resolves the plan by feature tag or stem, then applies each
        operation through the plan step-ops core that owns canonical
        identifiers and the gap-no-reuse rule. Operations apply sequentially
        against one parsed plan and item failures do not abort the batch; the
        plan is serialised and written once at the end. Phase and wave
        operations are not first-class here - they live behind the gateway.

        Args:
            ctx: The MCP request context.
            plan: A feature tag or plan stem/path addressing one plan.
            operations: The batch of step-authoring operations.

        Returns:
            The :class:`PlanEditResult` with per-operation outcomes and the
            post-batch completion facts.

        Raises:
            ValueError: When ``operations`` is empty or the plan address does
                not resolve to a unique plan.
        """
        from ..plan_resolver import PlanResolutionError, resolve_plan

        if not operations:
            raise ValueError("plan_edit requires at least one operation")

        root_dir = _get_ctx().target_dir
        try:
            resolved = resolve_plan(root_dir, plan)
        except PlanResolutionError as exc:
            raise ValueError(str(exc)) from exc

        await ctx.info(f"plan_edit: {resolved.stem} {len(operations)} op(s)")

        parsed, original_text = _load_plan(resolved.path)
        items: list[PlanEditItemResult] = []
        expected_retired: set[str] = set()
        changed = False

        for op in operations:
            item = _apply_plan_edit(parsed, op)
            items.append(item)
            if item.status != "failed":
                changed = True
                # A ``remove`` legitimately retires its target id; declaring it
                # here keeps the shared write guard from mistaking the intended
                # retirement for a serialisation conflict.
                if item.status == "removed" and item.step_id is not None:
                    expected_retired.add(item.step_id)

        if changed:
            _save_plan(
                resolved.path, parsed, original_text, expected_retired=expected_retired
            )

        total, completed, _percent, next_open = _progress_summary(parsed)
        return PlanEditResult(
            status=_reduce(
                [i.status for i in items], {"created", "updated", "removed"}
            ),
            plan=resolved.stem,
            items=items,
            total_steps=total,
            steps_completed=completed,
            next_open_step=next_open,
        )


def _apply_plan_edit(plan: Plan, op: PlanEditOperation) -> PlanEditItemResult:
    """Apply one ``plan_edit`` operation, folding failures into an item result.

    Every mutation routes through the plan step-ops core; a violated
    precondition (a missing action, an unknown anchor, an unresolvable step)
    surfaces as a per-item ``failed`` rather than aborting the batch.

    Args:
        plan: The parsed plan, mutated in place on success.
        op: The operation to apply.

    Returns:
        The per-operation :class:`PlanEditItemResult`.
    """
    from ...plan.commands._errors import PlanCommandError
    from ...plan.commands.step_ops import add_step, edit_step, insert_step, remove_step

    def _fail(message: str) -> PlanEditItemResult:
        return PlanEditItemResult(
            operation=op.operation, status="failed", error={"message": message}
        )

    try:
        if op.operation == "add":
            if op.action is None or op.scope is None:
                return _fail("'add' requires 'action' and 'scope'")
            step = add_step(
                plan, action=op.action, scope=op.scope, phase_id=op.phase_id
            )
            return PlanEditItemResult(
                operation="add", status="created", step_id=step.canonical_id
            )
        if op.operation == "insert":
            if op.action is None or op.scope is None:
                return _fail("'insert' requires 'action' and 'scope'")
            step = insert_step(
                plan,
                action=op.action,
                scope=op.scope,
                before=op.before,
                after=op.after,
            )
            return PlanEditItemResult(
                operation="insert", status="created", step_id=step.canonical_id
            )
        if op.operation == "edit":
            if op.step_id is None:
                return _fail("'edit' requires 'step_id'")
            step = edit_step(plan, op.step_id, action=op.action, scope=op.scope)
            return PlanEditItemResult(
                operation="edit", status="updated", step_id=step.canonical_id
            )
        if op.operation == "remove":
            if op.step_id is None:
                return _fail("'remove' requires 'step_id'")
            retired = remove_step(plan, op.step_id)
            return PlanEditItemResult(
                operation="remove", status="removed", step_id=retired
            )
        return _fail(f"Unknown plan_edit operation: {op.operation!r}")
    except PlanCommandError as exc:
        return _fail(str(exc))
