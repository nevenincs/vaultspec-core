"""Typer wiring for ``vaultspec-core vault plan ...`` subcommand group.

Registers the read commands (``status``, ``check``, ``query``) and the
container-level mutating verbs (``step``/``phase``/``wave`` add/insert/
move/edit/check/uncheck/toggle/edit/remove, ``epic intent``, ``tier``).

Each command is a thin Typer wrapper over the pure-Python handlers in
:mod:`vaultspec_core.plan` and :mod:`vaultspec_core.plan.commands`. The
wrapper parses CLI arguments, opens the plan file, dispatches the
handler, serialises back to disk, and emits the appropriate human or
JSON output.
"""

import json
import sys
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Annotated, Any, cast

import typer

from vaultspec_core.cli._target import TargetOption

__all__ = ["plan_app"]

# Defensive ceiling for serialised plan output (issue #125). A legitimate
# single structural edit never multiplies a plan several times over, so output
# beyond ``max(_PLAN_GROWTH_FLOOR, _PLAN_GROWTH_FACTOR * len(source))`` signals a
# serialiser fault and the write is refused. The floor keeps tiny plans editable.
_PLAN_GROWTH_FLOOR = 65_536
_PLAN_GROWTH_FACTOR = 4


def _render_user_errors[F: Callable[..., None]](func: F) -> F:
    """Render handler-raised typed errors as one-line CLI messages.

    Every command-handler typed exception inherits from
    :class:`PlanCommandError`; the decorator catches that single base
    so adding a new typed error requires no change here as long as it
    inherits from the marker. The catch surfaces ``error: <message>``
    on stderr and exits 1.

    Programmer-error exceptions (assertions, raw ``ValueError`` from
    internal invariants that did not go through a typed wrapper) are
    not caught; they propagate so test runs and CI surface the bug.
    """
    from vaultspec_core.plan.commands._errors import PlanCommandError

    @wraps(func)
    def wrapper(*args: object, **kwargs: object) -> None:
        try:
            func(*args, **kwargs)
        except PlanCommandError as exc:
            typer.echo(f"error: {exc}", err=True)
            raise typer.Exit(1) from exc

    return cast("F", wrapper)


def _save_plan_or_dry_run(
    path: Path,
    plan: Any,
    original_text: str,
    dry_run: bool,
    canonicalise: bool,
    success_msg: str,
    expected_retired: set[str] | None = None,
) -> None:
    """Helper to serialise plan and output a unified diff on dry-run.

    Or write to disk on apply.
    """
    from vaultspec_core.plan.commands._errors import PlanCommandError
    from vaultspec_core.plan.parser import parse_plan
    from vaultspec_core.plan.serialiser import serialise_plan

    new_text = serialise_plan(plan, canonicalise=canonicalise)

    # Issue 150: Verify that no unexpected elements are retired during this mutation
    try:
        old_plan = parse_plan(original_text)
        new_plan = parse_plan(new_text)
    except Exception as exc:
        raise PlanCommandError(f"Plan validation failed during parsing: {exc}") from exc

    old_retired = (
        old_plan.retired_step_ids
        | old_plan.retired_phase_ids
        | old_plan.retired_wave_ids
    )
    new_retired = (
        new_plan.retired_step_ids
        | new_plan.retired_phase_ids
        | new_plan.retired_wave_ids
    )
    newly_retired = new_retired - old_retired

    expected = expected_retired if expected_retired is not None else set()
    unexpected = newly_retired - expected
    if unexpected:
        sorted_unexpected = sorted(unexpected)
        raise PlanCommandError(
            f"mutation aborted: unexpected retirement of active plan items: "
            f"{', '.join(sorted_unexpected)}. This indicates a serialization conflict."
        )

    # Defence in depth against a serialiser regression that multiplies authored
    # prose (issue #125): a single structural edit never grows a plan several
    # times over, so refuse to persist pathological output rather than corrupt
    # the file or exhaust the disk. The byte floor keeps tiny plans editable.
    growth_ceiling = max(_PLAN_GROWTH_FLOOR, _PLAN_GROWTH_FACTOR * len(original_text))
    if len(new_text) > growth_ceiling:
        raise PlanCommandError(
            f"refusing to write {path.name}: serialised output "
            f"({len(new_text)} bytes) is implausibly larger than the source "
            f"({len(original_text)} bytes); this indicates a serialiser fault, "
            "not an intended edit. The file on disk was left unchanged."
        )

    if dry_run:
        import difflib

        diff = difflib.unified_diff(
            original_text.splitlines(keepends=True),
            new_text.splitlines(keepends=True),
            fromfile=f"a/{path.name}",
            tofile=f"b/{path.name}",
        )
        diff_str = "".join(diff)
        if diff_str:
            typer.echo(diff_str)
        else:
            typer.echo("No changes.")
    else:
        if new_text != original_text:
            path.write_text(new_text, encoding="utf-8")
        preserved_count = 0 if canonicalise else len(plan.unknown_blocks)
        typer.echo(f"{success_msg} (Preserved {preserved_count} unknown blocks)")


plan_app = typer.Typer(
    help="Plan-document inspection and manipulation per the plan-hardening convention.",
    no_args_is_help=True,
)

step_app = typer.Typer(
    help=(
        "Step-level operations "
        "(add / insert / move / remove / check / uncheck / toggle / edit)."
    ),
    no_args_is_help=True,
)
plan_app.add_typer(step_app, name="step")

phase_app = typer.Typer(
    help="Phase-level operations (add / insert / move / remove / edit).",
    no_args_is_help=True,
)
plan_app.add_typer(phase_app, name="phase")

wave_app = typer.Typer(
    help="Wave-level operations (add / insert / move / remove / edit).",
    no_args_is_help=True,
)
plan_app.add_typer(wave_app, name="wave")

epic_app = typer.Typer(
    help="Epic-level operations (intent show / edit; L4 only).",
    no_args_is_help=True,
)
plan_app.add_typer(epic_app, name="epic")

tier_app = typer.Typer(
    help="Tier inspection and promotion / demotion.",
    no_args_is_help=True,
)
plan_app.add_typer(tier_app, name="tier")


# ---- Read commands ----------------------------------------------------------


@plan_app.command("status")
def cmd_status(
    path: Annotated[Path, typer.Argument(help="Plan document path")],
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit JSON instead of human form")
    ] = False,
    target: TargetOption = None,
) -> None:
    """Report plan health, structure, and completion."""
    from vaultspec_core.cli._target import apply_target

    apply_target(target)

    from vaultspec_core.core.types import get_context as _get_ctx
    from vaultspec_core.plan.parser import parse_plan
    from vaultspec_core.plan.status import collect_status, status_to_json_dict

    plan = parse_plan(path)
    status = collect_status(plan, root_dir=_get_ctx().target_dir)

    if json_output:
        from vaultspec_core.cli.rendering import json_envelope

        envelope = json_envelope(
            "vault.plan.status", "unchanged", status_to_json_dict(status)
        )
        typer.echo(json.dumps(envelope, indent=2))
        return

    typer.echo(f"Plan: {path}")
    typer.echo(f"Tier: {status.tier.value}")
    if status.legacy_tier_default:
        typer.echo(
            "  (legacy plan; tier defaulted to L2 - run a writer to add the field)"
        )
    typer.echo(
        f"Counts: {status.wave_count} Waves, {status.phase_count} Phases, "
        f"{status.step_count} Steps"
    )
    typer.echo(
        f"Completion: {status.steps_completed} of {status.step_count} "
        f"({status.completion_percent}%)"
    )
    if status.exec_missing_ids:
        missing_ids_str = ", ".join(status.exec_missing_ids)
        hint = typer.style(
            f"! exec-missing: checked steps lacking execution records: "
            f"{missing_ids_str}",
            fg=typer.colors.YELLOW,
        )
        typer.echo(hint)


@plan_app.command("check")
def cmd_check(
    path: Annotated[Path, typer.Argument(help="Plan document path")],
    fix: Annotated[
        bool,
        typer.Option("--fix", help="Apply autofixable transformations idempotently"),
    ] = False,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit findings as JSON")
    ] = False,
) -> None:
    """Validate convention compliance; with ``--fix``, apply autofixes."""
    from vaultspec_core.plan.checks import collect_all, has_errors
    from vaultspec_core.plan.fixes import apply_all_fixes
    from vaultspec_core.plan.parser import parse_plan

    text = path.read_text(encoding="utf-8")

    if fix:
        fixed_text = apply_all_fixes(text)
        if fixed_text != text:
            path.write_text(fixed_text, encoding="utf-8")
        text = fixed_text

    plan = parse_plan(text)
    findings = collect_all(plan, text)

    if json_output:
        from vaultspec_core.cli.rendering import json_envelope

        findings_data = [
            {
                "code": f.code,
                "severity": f.severity.value,
                "message": f.message,
                "line": f.line_number,
                "fix_hint": f.fix_hint,
                "autofixable": f.autofixable,
            }
            for f in findings
        ]
        status = "failed" if has_errors(findings) else "unchanged"
        envelope = json_envelope(
            "vault.plan.check", status, {"findings": findings_data}
        )
        typer.echo(json.dumps(envelope, indent=2))
    else:
        for finding in findings:
            typer.echo(
                f"[{finding.severity.value}] {finding.code} "
                f"line {finding.line_number}: {finding.message}"
            )
            # Surface the fix hint in the text output too - it used to be
            # reachable only via --json - and label whether --fix can
            # apply it or the operator must act manually.
            if finding.fix_hint:
                tag = "autofix" if finding.autofixable else "manual"
                typer.echo(f"  fix ({tag}): {finding.fix_hint}")

    if has_errors(findings):
        sys.exit(1)


@plan_app.command("query")
def cmd_query(
    path: Annotated[Path, typer.Argument(help="Plan document path")],
    open_only: Annotated[
        bool, typer.Option("--open", help="Only Steps with [ ] checkbox")
    ] = False,
    closed_only: Annotated[
        bool, typer.Option("--closed", help="Only Steps with [x] checkbox")
    ] = False,
    in_phase: Annotated[
        str | None, typer.Option("--phase", help="Restrict to Phase P##")
    ] = None,
    in_wave: Annotated[
        str | None, typer.Option("--wave", help="Restrict to Wave W##")
    ] = None,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit matched Steps as JSON")
    ] = False,
) -> None:
    """Filter Step rows by container scope and open/closed predicate."""
    from vaultspec_core.plan.parser import parse_plan
    from vaultspec_core.plan.query import QueryFilter, query_steps

    plan = parse_plan(path)
    result = query_steps(
        plan,
        QueryFilter(
            scope_phase=in_phase,
            scope_wave=in_wave,
            only_open=open_only,
            only_closed=closed_only,
        ),
    )
    if json_output:
        from vaultspec_core.cli.rendering import json_envelope

        payload = {
            "matched": len(result.matched),
            "total": result.total,
            "steps": [
                {
                    "display_path": step.display_path,
                    "checked": step.checked,
                    "action": step.action,
                    "scope": step.scope,
                }
                for step in result.matched
            ],
        }
        typer.echo(
            json.dumps(
                json_envelope("vault.plan.query", "unchanged", payload), indent=2
            )
        )
        return
    typer.echo(f"Matched {len(result.matched)} of {result.total} Steps:")
    for step in result.matched:
        state = "x" if step.checked else " "
        typer.echo(
            f"- [{state}] `{step.display_path}` - {step.action}; `{step.scope}`."
        )


# ---- Step commands ----------------------------------------------------------


@step_app.command("toggle")
@_render_user_errors
def cmd_step_toggle(
    path: Annotated[Path, typer.Argument(help="Plan document path")],
    step_id: Annotated[str, typer.Argument(help="Step canonical id (S##)")],
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview changes without writing to disk"),
    ] = False,
    canonicalise: Annotated[
        bool,
        typer.Option(
            "--canonicalise", help="Strip unknown prose blocks during serialization"
        ),
    ] = False,
) -> None:
    """Flip the Step's checkbox state."""
    from vaultspec_core.plan.commands.step_ops import toggle_step
    from vaultspec_core.plan.parser import parse_plan

    original_text = path.read_text(encoding="utf-8")
    plan = parse_plan(original_text)
    step = toggle_step(plan, step_id)
    new_state = "closed" if step.checked else "open"
    _save_plan_or_dry_run(
        path=path,
        plan=plan,
        original_text=original_text,
        dry_run=dry_run,
        canonicalise=canonicalise,
        success_msg=f"Toggled Step `{step.canonical_id}` to {new_state}.",
    )


@step_app.command("check")
@_render_user_errors
def cmd_step_check(
    path: Annotated[Path, typer.Argument(help="Plan document path")],
    step_id: Annotated[str, typer.Argument(help="Step canonical id (S##)")],
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview changes without writing to disk"),
    ] = False,
    canonicalise: Annotated[
        bool,
        typer.Option(
            "--canonicalise", help="Strip unknown prose blocks during serialization"
        ),
    ] = False,
) -> None:
    """Mark the Step closed (idempotent)."""
    from vaultspec_core.plan.commands.step_ops import check_step
    from vaultspec_core.plan.parser import parse_plan

    original_text = path.read_text(encoding="utf-8")
    plan = parse_plan(original_text)
    check_step(plan, step_id)
    _save_plan_or_dry_run(
        path=path,
        plan=plan,
        original_text=original_text,
        dry_run=dry_run,
        canonicalise=canonicalise,
        success_msg=f"Closed Step `{step_id}`.",
    )


@step_app.command("uncheck")
@_render_user_errors
def cmd_step_uncheck(
    path: Annotated[Path, typer.Argument(help="Plan document path")],
    step_id: Annotated[str, typer.Argument(help="Step canonical id (S##)")],
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview changes without writing to disk"),
    ] = False,
    canonicalise: Annotated[
        bool,
        typer.Option(
            "--canonicalise", help="Strip unknown prose blocks during serialization"
        ),
    ] = False,
) -> None:
    """Mark the Step open (idempotent)."""
    from vaultspec_core.plan.commands.step_ops import uncheck_step
    from vaultspec_core.plan.parser import parse_plan

    original_text = path.read_text(encoding="utf-8")
    plan = parse_plan(original_text)
    uncheck_step(plan, step_id)
    _save_plan_or_dry_run(
        path=path,
        plan=plan,
        original_text=original_text,
        dry_run=dry_run,
        canonicalise=canonicalise,
        success_msg=f"Re-opened Step `{step_id}`.",
    )


# ---- Step add / insert / edit / move / remove ------------------------------


@step_app.command("add")
@_render_user_errors
def cmd_step_add(
    path: Annotated[Path, typer.Argument(help="Plan document path")],
    action: Annotated[str, typer.Option("--action", help="Imperative-verb statement")],
    scope: Annotated[str, typer.Option("--scope", help="`path/to/file` scope clause")],
    phase_id: Annotated[
        str | None,
        typer.Option(
            "--phase",
            help="Parent Phase id (required at L2+, omitted at L1)",
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview changes without writing to disk"),
    ] = False,
    canonicalise: Annotated[
        bool,
        typer.Option(
            "--canonicalise", help="Strip unknown prose blocks during serialization"
        ),
    ] = False,
) -> None:
    """Append a new Step at the next-available canonical id."""
    from vaultspec_core.plan.commands.step_ops import add_step
    from vaultspec_core.plan.parser import parse_plan

    original_text = path.read_text(encoding="utf-8")
    plan = parse_plan(original_text)
    step = add_step(plan, action=action, scope=scope, phase_id=phase_id)
    _save_plan_or_dry_run(
        path=path,
        plan=plan,
        original_text=original_text,
        dry_run=dry_run,
        canonicalise=canonicalise,
        success_msg=f"Added Step `{step.display_path}`.",
    )


@step_app.command("insert")
@_render_user_errors
def cmd_step_insert(
    path: Annotated[Path, typer.Argument(help="Plan document path")],
    action: Annotated[str, typer.Option("--action", help="Imperative-verb statement")],
    scope: Annotated[str, typer.Option("--scope", help="`path/to/file` scope clause")],
    before: Annotated[
        str | None,
        typer.Option("--before", help="Anchor Step id; the new row precedes it"),
    ] = None,
    after: Annotated[
        str | None,
        typer.Option("--after", help="Anchor Step id; the new row follows it"),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview changes without writing to disk"),
    ] = False,
    canonicalise: Annotated[
        bool,
        typer.Option(
            "--canonicalise", help="Strip unknown prose blocks during serialization"
        ),
    ] = False,
) -> None:
    """Insert a Step at a named position relative to an existing anchor."""
    from vaultspec_core.plan.commands.step_ops import insert_step
    from vaultspec_core.plan.parser import parse_plan

    original_text = path.read_text(encoding="utf-8")
    plan = parse_plan(original_text)
    step = insert_step(plan, action=action, scope=scope, before=before, after=after)
    _save_plan_or_dry_run(
        path=path,
        plan=plan,
        original_text=original_text,
        dry_run=dry_run,
        canonicalise=canonicalise,
        success_msg=f"Inserted Step `{step.display_path}`.",
    )


@step_app.command("edit")
@_render_user_errors
def cmd_step_edit(
    path: Annotated[Path, typer.Argument(help="Plan document path")],
    step_id: Annotated[str, typer.Argument(help="Step canonical id (S##)")],
    action: Annotated[
        str | None, typer.Option("--action", help="New imperative-verb statement")
    ] = None,
    scope: Annotated[
        str | None, typer.Option("--scope", help="New `path/to/file` scope clause")
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview changes without writing to disk"),
    ] = False,
    canonicalise: Annotated[
        bool,
        typer.Option(
            "--canonicalise", help="Strip unknown prose blocks during serialization"
        ),
    ] = False,
) -> None:
    """Edit the Step's action and / or scope without changing its identifier."""
    from vaultspec_core.plan.commands.step_ops import edit_step
    from vaultspec_core.plan.parser import parse_plan

    original_text = path.read_text(encoding="utf-8")
    plan = parse_plan(original_text)
    edit_step(plan, step_id, action=action, scope=scope)
    _save_plan_or_dry_run(
        path=path,
        plan=plan,
        original_text=original_text,
        dry_run=dry_run,
        canonicalise=canonicalise,
        success_msg=f"Edited Step `{step_id}`.",
    )


@step_app.command("move")
@_render_user_errors
def cmd_step_move(
    path: Annotated[Path, typer.Argument(help="Plan document path")],
    step_id: Annotated[str, typer.Argument(help="Step canonical id (S##)")],
    to_phase: Annotated[
        str | None, typer.Option("--to-phase", help="Re-parent under this Phase id")
    ] = None,
    before: Annotated[
        str | None, typer.Option("--before", help="Place before this anchor Step")
    ] = None,
    after: Annotated[
        str | None, typer.Option("--after", help="Place after this anchor Step")
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview changes without writing to disk"),
    ] = False,
    canonicalise: Annotated[
        bool,
        typer.Option(
            "--canonicalise", help="Strip unknown prose blocks during serialization"
        ),
    ] = False,
) -> None:
    """Re-parent and / or re-position a Step per the move-flag precedence rule."""
    from vaultspec_core.plan.commands.step_ops import move_step
    from vaultspec_core.plan.parser import parse_plan

    original_text = path.read_text(encoding="utf-8")
    plan = parse_plan(original_text)
    step = move_step(plan, step_id, to_phase=to_phase, before=before, after=after)
    _save_plan_or_dry_run(
        path=path,
        plan=plan,
        original_text=original_text,
        dry_run=dry_run,
        canonicalise=canonicalise,
        success_msg=f"Moved Step `{step.display_path}`.",
    )


@step_app.command("remove")
@_render_user_errors
def cmd_step_remove(
    path: Annotated[Path, typer.Argument(help="Plan document path")],
    step_id: Annotated[str, typer.Argument(help="Step canonical id (S##)")],
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview changes without writing to disk"),
    ] = False,
    canonicalise: Annotated[
        bool,
        typer.Option(
            "--canonicalise", help="Strip unknown prose blocks during serialization"
        ),
    ] = False,
) -> None:
    """Remove a Step; its identifier is retired and never reused."""
    from vaultspec_core.plan.commands.step_ops import remove_step
    from vaultspec_core.plan.parser import parse_plan

    original_text = path.read_text(encoding="utf-8")
    plan = parse_plan(original_text)
    retired = remove_step(plan, step_id)
    _save_plan_or_dry_run(
        path=path,
        plan=plan,
        original_text=original_text,
        dry_run=dry_run,
        canonicalise=canonicalise,
        success_msg=f"Retired Step `{retired}`.",
        expected_retired={retired},
    )


# ---- Phase add / insert / edit / move / remove -----------------------------


@phase_app.command("add")
@_render_user_errors
def cmd_phase_add(
    path: Annotated[Path, typer.Argument(help="Plan document path")],
    title: Annotated[str, typer.Option("--title", help="Phase heading title")],
    intent: Annotated[str, typer.Option("--intent", help="Phase intent paragraph")],
    wave_id: Annotated[
        str | None, typer.Option("--wave", help="Parent Wave id (L3+ only)")
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview changes without writing to disk"),
    ] = False,
    canonicalise: Annotated[
        bool,
        typer.Option(
            "--canonicalise", help="Strip unknown prose blocks during serialization"
        ),
    ] = False,
) -> None:
    """Append a new Phase at the next-available canonical id."""
    from vaultspec_core.plan.commands.phase_ops import add_phase
    from vaultspec_core.plan.parser import parse_plan

    original_text = path.read_text(encoding="utf-8")
    plan = parse_plan(original_text)
    phase = add_phase(plan, title=title, intent=intent, wave_id=wave_id)
    _save_plan_or_dry_run(
        path=path,
        plan=plan,
        original_text=original_text,
        dry_run=dry_run,
        canonicalise=canonicalise,
        success_msg=f"Added Phase `{phase.display_path}`.",
    )


@phase_app.command("insert")
@_render_user_errors
def cmd_phase_insert(
    path: Annotated[Path, typer.Argument(help="Plan document path")],
    title: Annotated[str, typer.Option("--title", help="Phase heading title")],
    intent: Annotated[str, typer.Option("--intent", help="Phase intent paragraph")],
    before: Annotated[
        str | None,
        typer.Option("--before", help="Anchor Phase id; new Phase precedes it"),
    ] = None,
    after: Annotated[
        str | None,
        typer.Option("--after", help="Anchor Phase id; new Phase follows it"),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview changes without writing to disk"),
    ] = False,
    canonicalise: Annotated[
        bool,
        typer.Option(
            "--canonicalise", help="Strip unknown prose blocks during serialization"
        ),
    ] = False,
) -> None:
    """Insert a Phase at a named position; parent Wave inferred from anchor."""
    from vaultspec_core.plan.commands.phase_ops import insert_phase
    from vaultspec_core.plan.parser import parse_plan

    original_text = path.read_text(encoding="utf-8")
    plan = parse_plan(original_text)
    phase = insert_phase(plan, title=title, intent=intent, before=before, after=after)
    _save_plan_or_dry_run(
        path=path,
        plan=plan,
        original_text=original_text,
        dry_run=dry_run,
        canonicalise=canonicalise,
        success_msg=f"Inserted Phase `{phase.display_path}`.",
    )


@phase_app.command("edit")
@_render_user_errors
def cmd_phase_edit(
    path: Annotated[Path, typer.Argument(help="Plan document path")],
    phase_id: Annotated[str, typer.Argument(help="Phase canonical id (P##)")],
    title: Annotated[
        str | None, typer.Option("--title", help="New Phase heading title")
    ] = None,
    intent: Annotated[
        str | None, typer.Option("--intent", help="New Phase intent paragraph")
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview changes without writing to disk"),
    ] = False,
    canonicalise: Annotated[
        bool,
        typer.Option(
            "--canonicalise", help="Strip unknown prose blocks during serialization"
        ),
    ] = False,
) -> None:
    """Edit the Phase's title and / or intent paragraph in place."""
    from vaultspec_core.plan.commands.phase_ops import edit_phase
    from vaultspec_core.plan.parser import parse_plan

    original_text = path.read_text(encoding="utf-8")
    plan = parse_plan(original_text)
    edit_phase(plan, phase_id, title=title, intent=intent)
    _save_plan_or_dry_run(
        path=path,
        plan=plan,
        original_text=original_text,
        dry_run=dry_run,
        canonicalise=canonicalise,
        success_msg=f"Edited Phase `{phase_id}`.",
    )


@phase_app.command("move")
@_render_user_errors
def cmd_phase_move(
    path: Annotated[Path, typer.Argument(help="Plan document path")],
    phase_id: Annotated[str, typer.Argument(help="Phase canonical id (P##)")],
    to_wave: Annotated[
        str | None, typer.Option("--to-wave", help="Re-parent under this Wave id")
    ] = None,
    before: Annotated[
        str | None, typer.Option("--before", help="Place before this anchor Phase")
    ] = None,
    after: Annotated[
        str | None, typer.Option("--after", help="Place after this anchor Phase")
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview changes without writing to disk"),
    ] = False,
    canonicalise: Annotated[
        bool,
        typer.Option(
            "--canonicalise", help="Strip unknown prose blocks during serialization"
        ),
    ] = False,
) -> None:
    """Re-parent and / or re-position a Phase."""
    from vaultspec_core.plan.commands.phase_ops import move_phase
    from vaultspec_core.plan.parser import parse_plan

    original_text = path.read_text(encoding="utf-8")
    plan = parse_plan(original_text)
    phase = move_phase(plan, phase_id, to_wave=to_wave, before=before, after=after)
    _save_plan_or_dry_run(
        path=path,
        plan=plan,
        original_text=original_text,
        dry_run=dry_run,
        canonicalise=canonicalise,
        success_msg=f"Moved Phase `{phase.display_path}`.",
    )


@phase_app.command("renumber")
@_render_user_errors
def cmd_phase_renumber(
    path: Annotated[Path, typer.Argument(help="Plan document path")],
    phase_id: Annotated[str, typer.Argument(help="Existing Phase canonical id (P##)")],
    to: Annotated[
        str,
        typer.Option(
            "--to",
            help="New canonical id (P##); must not collide with live or retired ids",
        ),
    ],
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview changes without writing to disk"),
    ] = False,
    canonicalise: Annotated[
        bool,
        typer.Option(
            "--canonicalise", help="Strip unknown prose blocks during serialization"
        ),
    ] = False,
) -> None:
    """Reassign a Phase's canonical id; descendant Step display paths recompute."""
    from vaultspec_core.plan.commands.phase_ops import renumber_phase
    from vaultspec_core.plan.parser import parse_plan

    original_text = path.read_text(encoding="utf-8")
    plan = parse_plan(original_text)
    phase = renumber_phase(plan, phase_id, to=to)
    _save_plan_or_dry_run(
        path=path,
        plan=plan,
        original_text=original_text,
        dry_run=dry_run,
        canonicalise=canonicalise,
        success_msg=f"Renumbered Phase `{phase_id}` to `{phase.canonical_id}`.",
    )


@phase_app.command("remove")
@_render_user_errors
def cmd_phase_remove(
    path: Annotated[Path, typer.Argument(help="Plan document path")],
    phase_id: Annotated[str, typer.Argument(help="Phase canonical id (P##)")],
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview changes without writing to disk"),
    ] = False,
    canonicalise: Annotated[
        bool,
        typer.Option(
            "--canonicalise", help="Strip unknown prose blocks during serialization"
        ),
    ] = False,
) -> None:
    """Remove a Phase; descendant Step ids cascade-retire."""
    from vaultspec_core.plan.commands.phase_ops import remove_phase
    from vaultspec_core.plan.parser import parse_plan

    original_text = path.read_text(encoding="utf-8")
    plan = parse_plan(original_text)
    retired_phase, retired_steps = remove_phase(plan, phase_id)
    cascaded_str = f"{', '.join(retired_steps) if retired_steps else '(none)'}"
    _save_plan_or_dry_run(
        path=path,
        plan=plan,
        original_text=original_text,
        dry_run=dry_run,
        canonicalise=canonicalise,
        success_msg=f"Retired Phase `{retired_phase}`; cascaded Steps: {cascaded_str}.",
        expected_retired={retired_phase} | set(retired_steps),
    )


# ---- Wave add / insert / edit / move / remove ------------------------------


@wave_app.command("add")
@_render_user_errors
def cmd_wave_add(
    path: Annotated[Path, typer.Argument(help="Plan document path")],
    title: Annotated[str, typer.Option("--title", help="Wave heading title")],
    intent: Annotated[str, typer.Option("--intent", help="Wave intent paragraph")],
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview changes without writing to disk"),
    ] = False,
    canonicalise: Annotated[
        bool,
        typer.Option(
            "--canonicalise", help="Strip unknown prose blocks during serialization"
        ),
    ] = False,
) -> None:
    """Append a new Wave at the next-available canonical id (L3+ only)."""
    from vaultspec_core.plan.commands.wave_ops import add_wave
    from vaultspec_core.plan.parser import parse_plan

    original_text = path.read_text(encoding="utf-8")
    plan = parse_plan(original_text)
    wave = add_wave(plan, title=title, intent=intent)
    _save_plan_or_dry_run(
        path=path,
        plan=plan,
        original_text=original_text,
        dry_run=dry_run,
        canonicalise=canonicalise,
        success_msg=f"Added Wave `{wave.canonical_id}`.",
    )


@wave_app.command("insert")
@_render_user_errors
def cmd_wave_insert(
    path: Annotated[Path, typer.Argument(help="Plan document path")],
    title: Annotated[str, typer.Option("--title", help="Wave heading title")],
    intent: Annotated[str, typer.Option("--intent", help="Wave intent paragraph")],
    before: Annotated[
        str | None,
        typer.Option("--before", help="Anchor Wave id; new Wave precedes it"),
    ] = None,
    after: Annotated[
        str | None,
        typer.Option("--after", help="Anchor Wave id; new Wave follows it"),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview changes without writing to disk"),
    ] = False,
    canonicalise: Annotated[
        bool,
        typer.Option(
            "--canonicalise", help="Strip unknown prose blocks during serialization"
        ),
    ] = False,
) -> None:
    """Insert a Wave at a named position relative to an existing anchor."""
    from vaultspec_core.plan.commands.wave_ops import insert_wave
    from vaultspec_core.plan.parser import parse_plan

    original_text = path.read_text(encoding="utf-8")
    plan = parse_plan(original_text)
    wave = insert_wave(plan, title=title, intent=intent, before=before, after=after)
    _save_plan_or_dry_run(
        path=path,
        plan=plan,
        original_text=original_text,
        dry_run=dry_run,
        canonicalise=canonicalise,
        success_msg=f"Inserted Wave `{wave.canonical_id}`.",
    )


@wave_app.command("edit")
@_render_user_errors
def cmd_wave_edit(
    path: Annotated[Path, typer.Argument(help="Plan document path")],
    wave_id: Annotated[str, typer.Argument(help="Wave canonical id (W##)")],
    title: Annotated[
        str | None, typer.Option("--title", help="New Wave heading title")
    ] = None,
    intent: Annotated[
        str | None, typer.Option("--intent", help="New Wave intent paragraph")
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview changes without writing to disk"),
    ] = False,
    canonicalise: Annotated[
        bool,
        typer.Option(
            "--canonicalise", help="Strip unknown prose blocks during serialization"
        ),
    ] = False,
) -> None:
    """Edit the Wave's title and / or intent paragraph in place."""
    from vaultspec_core.plan.commands.wave_ops import edit_wave
    from vaultspec_core.plan.parser import parse_plan

    original_text = path.read_text(encoding="utf-8")
    plan = parse_plan(original_text)
    edit_wave(plan, wave_id, title=title, intent=intent)
    _save_plan_or_dry_run(
        path=path,
        plan=plan,
        original_text=original_text,
        dry_run=dry_run,
        canonicalise=canonicalise,
        success_msg=f"Edited Wave `{wave_id}`.",
    )


@wave_app.command("move")
@_render_user_errors
def cmd_wave_move(
    path: Annotated[Path, typer.Argument(help="Plan document path")],
    wave_id: Annotated[str, typer.Argument(help="Wave canonical id (W##)")],
    before: Annotated[
        str | None, typer.Option("--before", help="Place before this anchor Wave")
    ] = None,
    after: Annotated[
        str | None, typer.Option("--after", help="Place after this anchor Wave")
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview changes without writing to disk"),
    ] = False,
    canonicalise: Annotated[
        bool,
        typer.Option(
            "--canonicalise", help="Strip unknown prose blocks during serialization"
        ),
    ] = False,
) -> None:
    """Re-position a Wave in document order."""
    from vaultspec_core.plan.commands.wave_ops import move_wave
    from vaultspec_core.plan.parser import parse_plan

    original_text = path.read_text(encoding="utf-8")
    plan = parse_plan(original_text)
    wave = move_wave(plan, wave_id, before=before, after=after)
    _save_plan_or_dry_run(
        path=path,
        plan=plan,
        original_text=original_text,
        dry_run=dry_run,
        canonicalise=canonicalise,
        success_msg=f"Moved Wave `{wave.canonical_id}`.",
    )


@wave_app.command("remove")
@_render_user_errors
def cmd_wave_remove(
    path: Annotated[Path, typer.Argument(help="Plan document path")],
    wave_id: Annotated[str, typer.Argument(help="Wave canonical id (W##)")],
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview changes without writing to disk"),
    ] = False,
    canonicalise: Annotated[
        bool,
        typer.Option(
            "--canonicalise", help="Strip unknown prose blocks during serialization"
        ),
    ] = False,
) -> None:
    """Remove a Wave; descendant Phase and Step ids cascade-retire."""
    from vaultspec_core.plan.commands.wave_ops import remove_wave
    from vaultspec_core.plan.parser import parse_plan

    original_text = path.read_text(encoding="utf-8")
    plan = parse_plan(original_text)
    retired_wave, retired_phases, retired_steps = remove_wave(plan, wave_id)
    phases_str = f"{', '.join(retired_phases) if retired_phases else '(none)'}"
    steps_str = f"{', '.join(retired_steps) if retired_steps else '(none)'}"
    _save_plan_or_dry_run(
        path=path,
        plan=plan,
        original_text=original_text,
        dry_run=dry_run,
        canonicalise=canonicalise,
        success_msg=(
            f"Retired Wave `{retired_wave}`; cascaded Phases: {phases_str}; "
            f"cascaded Steps: {steps_str}."
        ),
        expected_retired={retired_wave} | set(retired_phases) | set(retired_steps),
    )


# ---- Epic intent (L4 only) -------------------------------------------------


epic_intent_app = typer.Typer(
    help="Show or edit the L4 plan's Epic intent paragraph.",
    no_args_is_help=True,
)
epic_app.add_typer(epic_intent_app, name="intent")


@epic_intent_app.command("show")
def cmd_epic_intent_show(
    path: Annotated[Path, typer.Argument(help="Plan document path")],
) -> None:
    """Print the Epic intent paragraph (L4 plans only)."""
    from vaultspec_core.plan.commands.epic_ops import show_epic_intent
    from vaultspec_core.plan.parser import parse_plan

    plan = parse_plan(path)
    typer.echo(show_epic_intent(plan))


@epic_intent_app.command("edit")
@_render_user_errors
def cmd_epic_intent_edit(
    path: Annotated[Path, typer.Argument(help="Plan document path")],
    text: Annotated[
        str,
        typer.Option(
            "--text", help="New Epic intent paragraph (must declare PM association)"
        ),
    ],
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview changes without writing to disk"),
    ] = False,
    canonicalise: Annotated[
        bool,
        typer.Option(
            "--canonicalise", help="Strip unknown prose blocks during serialization"
        ),
    ] = False,
) -> None:
    """Replace the Epic intent paragraph (L4 plans only)."""
    from vaultspec_core.plan.commands.epic_ops import edit_epic_intent
    from vaultspec_core.plan.parser import parse_plan

    original_text = path.read_text(encoding="utf-8")
    plan = parse_plan(original_text)
    edit_epic_intent(plan, text=text)
    _save_plan_or_dry_run(
        path=path,
        plan=plan,
        original_text=original_text,
        dry_run=dry_run,
        canonicalise=canonicalise,
        success_msg="Edited Epic intent.",
    )


# ---- Tier commands ----------------------------------------------------------


@tier_app.command("show")
def cmd_tier_show(
    path: Annotated[Path, typer.Argument(help="Plan document path")],
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit the tier as JSON")
    ] = False,
) -> None:
    """Print the plan's declared tier."""
    from vaultspec_core.plan.commands.tier_ops import current_tier
    from vaultspec_core.plan.parser import parse_plan

    plan = parse_plan(path)
    tier = current_tier(plan).value
    if json_output:
        from vaultspec_core.cli.rendering import json_envelope

        typer.echo(
            json.dumps(
                json_envelope("vault.plan.tier.show", "unchanged", {"tier": tier}),
                indent=2,
            )
        )
        return
    typer.echo(tier)


@tier_app.command("promote")
@_render_user_errors
def cmd_tier_promote(
    path: Annotated[Path, typer.Argument(help="Plan document path")],
    target: Annotated[
        str | None,
        typer.Option(
            "--target",
            help="Target tier (L2/L3/L4); defaults to one tier above current",
        ),
    ] = None,
    phase_title: Annotated[
        str | None,
        typer.Option("--phase-title", help="Title for the synthesised P01"),
    ] = None,
    phase_intent: Annotated[
        str | None,
        typer.Option("--phase-intent", help="Intent for the synthesised P01"),
    ] = None,
    wave_title: Annotated[
        str | None,
        typer.Option("--wave-title", help="Title for the synthesised W01"),
    ] = None,
    wave_intent: Annotated[
        str | None,
        typer.Option("--wave-intent", help="Intent for the synthesised W01"),
    ] = None,
    epic_intent: Annotated[
        str | None,
        typer.Option(
            "--epic-intent",
            help="Epic intent paragraph (must declare PM association)",
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview changes without writing to disk"),
    ] = False,
    canonicalise: Annotated[
        bool,
        typer.Option(
            "--canonicalise", help="Strip unknown prose blocks during serialization"
        ),
    ] = False,
) -> None:
    """Promote the plan tier transitively (L1 -> ... -> L4).

    Promotion paths that introduce new containers require explicit
    title/intent flags for those containers. L1 -> L2 requires
    ``--phase-title`` and ``--phase-intent``; L2 -> L3 requires
    ``--wave-title`` and ``--wave-intent``; L3 -> L4 requires
    ``--epic-intent``. Transitive promotions (e.g. L1 -> L4) require
    the union of the relevant flag sets. The CLI refuses to write
    ``TODO:`` placeholders into the plan document; the operator must
    supply real values up front.
    """
    from vaultspec_core.console import get_console
    from vaultspec_core.plan.commands.tier_ops import promote_tier
    from vaultspec_core.plan.frontmatter import Tier
    from vaultspec_core.plan.parser import parse_plan

    console = get_console()

    original_text = path.read_text(encoding="utf-8")
    plan = parse_plan(original_text)
    current_tier_value = plan.frontmatter.tier.value
    target_tier = Tier(target) if target is not None else None

    # Determine which transitions will be made and validate the matching
    # flag sets are populated. Refuses to substitute TODO placeholders.
    tier_order = ["L1", "L2", "L3", "L4"]
    if target_tier is None:
        # Default: advance one tier.
        try:
            current_idx = tier_order.index(current_tier_value)
        except ValueError:
            current_idx = 0
        if current_idx + 1 >= len(tier_order):
            target_value = current_tier_value
        else:
            target_value = tier_order[current_idx + 1]
    else:
        target_value = target_tier.value

    # An invalid current tier (e.g. a hand-mangled plan) must not silently
    # empty the transitions list and bypass the mandatory-flag checks:
    # default current_idx to 0 so every container-introducing tier up to
    # the target is still validated. target_value is always a valid tier
    # (derived from tier_order or a validated Tier), so its lookup is not
    # guarded.
    try:
        current_idx = tier_order.index(current_tier_value)
    except ValueError:
        current_idx = 0
    target_idx = tier_order.index(target_value)
    transitions = tier_order[current_idx + 1 : target_idx + 1]

    missing: list[str] = []
    if "L2" in transitions:
        if phase_title is None:
            missing.append("--phase-title")
        if phase_intent is None:
            missing.append("--phase-intent")
    if "L3" in transitions:
        if wave_title is None:
            missing.append("--wave-title")
        if wave_intent is None:
            missing.append("--wave-intent")
    if "L4" in transitions and epic_intent is None:
        missing.append("--epic-intent")

    if missing:
        console.print(
            f"[red]Cannot promote {current_tier_value} -> {target_value} "
            f"without the following flag(s): {', '.join(missing)}.[/red]"
        )
        console.print(
            "[dim]Each promotion path that introduces a new container "
            "requires its title/intent up front; the CLI does not write "
            "TODO placeholders into plan documents.[/dim]"
        )
        raise typer.Exit(code=1)

    new_tier = promote_tier(
        plan,
        target=target_tier,
        phase_title=phase_title,
        phase_intent=phase_intent,
        wave_title=wave_title,
        wave_intent=wave_intent,
        epic_intent=epic_intent,
    )
    _save_plan_or_dry_run(
        path=path,
        plan=plan,
        original_text=original_text,
        dry_run=dry_run,
        canonicalise=canonicalise,
        success_msg=f"Tier promoted to {new_tier.value}.",
    )


@tier_app.command("demote")
@_render_user_errors
def cmd_tier_demote(
    path: Annotated[Path, typer.Argument(help="Plan document path")],
    target: Annotated[
        str | None,
        typer.Option(
            "--target",
            help="Target tier (L1/L2/L3); defaults to one tier below current",
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Override the multi-child collapse refusal; descendant ids retire",
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview changes without writing to disk"),
    ] = False,
    canonicalise: Annotated[
        bool,
        typer.Option(
            "--canonicalise", help="Strip unknown prose blocks during serialization"
        ),
    ] = False,
) -> None:
    """Demote the plan tier; refuses multi-child collapse without ``--force``."""
    from vaultspec_core.plan.commands.tier_ops import demote_tier
    from vaultspec_core.plan.frontmatter import Tier
    from vaultspec_core.plan.parser import parse_plan

    original_text = path.read_text(encoding="utf-8")
    plan = parse_plan(original_text)
    target_tier = Tier(target) if target is not None else None

    # Calculate expected_retired before we mutate the plan
    expected_retired: set[str] = set()
    current_t = plan.frontmatter.tier
    resolved_target = target_tier
    if resolved_target is None:
        from vaultspec_core.plan.commands.tier_ops import _previous_tier

        resolved_target = _previous_tier(current_t)

    if resolved_target is not None:
        if current_t in (Tier.L4, Tier.L3) and resolved_target is Tier.L2:
            expected_retired.update(w.canonical_id for w in plan.waves)
        elif current_t in (Tier.L4, Tier.L3, Tier.L2) and resolved_target is Tier.L1:
            expected_retired.update(w.canonical_id for w in plan.waves)
            expected_retired.update(p.canonical_id for p in plan.phases)

    new_tier = demote_tier(plan, target=target_tier, force=force)
    _save_plan_or_dry_run(
        path=path,
        plan=plan,
        original_text=original_text,
        dry_run=dry_run,
        canonicalise=canonicalise,
        success_msg=f"Tier demoted to {new_tier.value}.",
        expected_retired=expected_retired,
    )
