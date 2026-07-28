"""Step-level ``vault plan step`` commands: toggle / check / uncheck / add /
insert / edit / move / remove.

Registers onto :data:`vaultspec_core.cli.plan_cmd_app.step_app`. Split out of
:mod:`vaultspec_core.cli.plan_cmd` along the Step container seam.
"""

from typing import Annotated

import typer

from vaultspec_core.cli._target import PlanPathArg
from vaultspec_core.cli.plan_cmd_app import step_app
from vaultspec_core.cli.plan_cmd_shared import (
    _render_user_errors,
    _save_plan_or_dry_run,
)

__all__ = [
    "cmd_step_add",
    "cmd_step_check",
    "cmd_step_edit",
    "cmd_step_insert",
    "cmd_step_move",
    "cmd_step_remove",
    "cmd_step_toggle",
    "cmd_step_uncheck",
]


@step_app.command("toggle")
@_render_user_errors
def cmd_step_toggle(
    path: PlanPathArg,
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
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
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
        json_output=json_output,
        command="vault.plan.step.toggle",
    )


@step_app.command("check")
@_render_user_errors
def cmd_step_check(
    path: PlanPathArg,
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
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
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
        json_output=json_output,
        command="vault.plan.step.check",
    )


@step_app.command("uncheck")
@_render_user_errors
def cmd_step_uncheck(
    path: PlanPathArg,
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
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
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
        json_output=json_output,
        command="vault.plan.step.uncheck",
    )


# ---- Step add / insert / edit / move / remove ------------------------------


@step_app.command("add")
@_render_user_errors
def cmd_step_add(
    path: PlanPathArg,
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
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
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
        json_output=json_output,
        command="vault.plan.step.add",
    )


@step_app.command("insert")
@_render_user_errors
def cmd_step_insert(
    path: PlanPathArg,
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
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
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
        json_output=json_output,
        command="vault.plan.step.insert",
    )


@step_app.command("edit")
@_render_user_errors
def cmd_step_edit(
    path: PlanPathArg,
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
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
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
        json_output=json_output,
        command="vault.plan.step.edit",
    )


@step_app.command("move")
@_render_user_errors
def cmd_step_move(
    path: PlanPathArg,
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
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
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
        json_output=json_output,
        command="vault.plan.step.move",
    )


@step_app.command("remove")
@_render_user_errors
def cmd_step_remove(
    path: PlanPathArg,
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
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
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
        json_output=json_output,
        command="vault.plan.step.remove",
    )
