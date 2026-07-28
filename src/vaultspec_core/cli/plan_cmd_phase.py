"""Phase-level ``vault plan phase`` commands: add / insert / edit / move /
renumber / remove.

Registers onto :data:`vaultspec_core.cli.plan_cmd_app.phase_app`. Split out of
:mod:`vaultspec_core.cli.plan_cmd` along the Phase container seam.
"""

from typing import Annotated

import typer

from vaultspec_core.cli._target import PlanPathArg
from vaultspec_core.cli.plan_cmd_app import phase_app
from vaultspec_core.cli.plan_cmd_shared import (
    _render_user_errors,
    _save_plan_or_dry_run,
)

__all__ = [
    "cmd_phase_add",
    "cmd_phase_edit",
    "cmd_phase_insert",
    "cmd_phase_move",
    "cmd_phase_remove",
    "cmd_phase_renumber",
]


@phase_app.command("add")
@_render_user_errors
def cmd_phase_add(
    path: PlanPathArg,
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
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
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
        json_output=json_output,
        command="vault.plan.phase.add",
    )


@phase_app.command("insert")
@_render_user_errors
def cmd_phase_insert(
    path: PlanPathArg,
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
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
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
        json_output=json_output,
        command="vault.plan.phase.insert",
    )


@phase_app.command("edit")
@_render_user_errors
def cmd_phase_edit(
    path: PlanPathArg,
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
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
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
        json_output=json_output,
        command="vault.plan.phase.edit",
    )


@phase_app.command("move")
@_render_user_errors
def cmd_phase_move(
    path: PlanPathArg,
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
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
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
        json_output=json_output,
        command="vault.plan.phase.move",
    )


@phase_app.command("renumber")
@_render_user_errors
def cmd_phase_renumber(
    path: PlanPathArg,
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
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
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
        json_output=json_output,
        command="vault.plan.phase.renumber",
    )


@phase_app.command("remove")
@_render_user_errors
def cmd_phase_remove(
    path: PlanPathArg,
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
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
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
        json_output=json_output,
        command="vault.plan.phase.remove",
    )
