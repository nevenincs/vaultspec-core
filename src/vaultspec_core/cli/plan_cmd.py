"""Typer wiring for ``vault plan ...`` subcommand group.

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
from pathlib import Path
from typing import Annotated

import typer

__all__ = ["plan_app"]


plan_app = typer.Typer(
    help="Plan-document inspection and manipulation per the plan-hardening convention.",
    no_args_is_help=True,
)

step_app = typer.Typer(
    help="Step-level operations (add / insert / move / remove / state / edit).",
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
) -> None:
    """Report plan health, structure, and completion."""
    from vaultspec_core.plan.parser import parse_plan
    from vaultspec_core.plan.status import collect_status, status_to_json_dict

    plan = parse_plan(path)
    status = collect_status(plan)

    if json_output:
        typer.echo(json.dumps(status_to_json_dict(status), indent=2))
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
        payload = [
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
        typer.echo(json.dumps(payload, indent=2))
    else:
        for finding in findings:
            typer.echo(
                f"[{finding.severity.value}] {finding.code} "
                f"line {finding.line_number}: {finding.message}"
            )

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
    typer.echo(f"Matched {len(result.matched)} of {result.total} Steps:")
    for step in result.matched:
        state = "x" if step.checked else " "
        typer.echo(
            f"- [{state}] `{step.display_path}` - {step.action}; `{step.scope}`."
        )


# ---- Step commands ----------------------------------------------------------


@step_app.command("toggle")
def cmd_step_toggle(
    path: Annotated[Path, typer.Argument(help="Plan document path")],
    step_id: Annotated[str, typer.Argument(help="Step canonical id (S##)")],
) -> None:
    """Flip the Step's checkbox state."""
    from vaultspec_core.plan.commands.step_ops import toggle_step
    from vaultspec_core.plan.parser import parse_plan
    from vaultspec_core.plan.serialiser import serialise_plan

    plan = parse_plan(path)
    toggle_step(plan, step_id)
    path.write_text(serialise_plan(plan), encoding="utf-8")


@step_app.command("check")
def cmd_step_check(
    path: Annotated[Path, typer.Argument(help="Plan document path")],
    step_id: Annotated[str, typer.Argument(help="Step canonical id (S##)")],
) -> None:
    """Mark the Step closed (idempotent)."""
    from vaultspec_core.plan.commands.step_ops import check_step
    from vaultspec_core.plan.parser import parse_plan
    from vaultspec_core.plan.serialiser import serialise_plan

    plan = parse_plan(path)
    check_step(plan, step_id)
    path.write_text(serialise_plan(plan), encoding="utf-8")


@step_app.command("uncheck")
def cmd_step_uncheck(
    path: Annotated[Path, typer.Argument(help="Plan document path")],
    step_id: Annotated[str, typer.Argument(help="Step canonical id (S##)")],
) -> None:
    """Mark the Step open (idempotent)."""
    from vaultspec_core.plan.commands.step_ops import uncheck_step
    from vaultspec_core.plan.parser import parse_plan
    from vaultspec_core.plan.serialiser import serialise_plan

    plan = parse_plan(path)
    uncheck_step(plan, step_id)
    path.write_text(serialise_plan(plan), encoding="utf-8")


# ---- Tier commands ----------------------------------------------------------


@tier_app.command("show")
def cmd_tier_show(
    path: Annotated[Path, typer.Argument(help="Plan document path")],
) -> None:
    """Print the plan's declared tier."""
    from vaultspec_core.plan.commands.tier_ops import current_tier
    from vaultspec_core.plan.parser import parse_plan

    plan = parse_plan(path)
    typer.echo(current_tier(plan).value)
