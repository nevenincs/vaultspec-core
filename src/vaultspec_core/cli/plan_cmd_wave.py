"""Wave-level ``vault plan wave`` commands: add / insert / edit / move / remove.

Registers onto :data:`vaultspec_core.cli.plan_cmd_app.wave_app`. Split out of
:mod:`vaultspec_core.cli.plan_cmd` along the Wave container seam.
"""

from typing import Annotated

import typer

from vaultspec_core.cli._target import PlanPathArg
from vaultspec_core.cli.plan_cmd_app import wave_app
from vaultspec_core.cli.plan_cmd_shared import (
    render_user_errors,
    save_plan_or_dry_run,
    serialise_plan_mutation,
)

__all__ = [
    "cmd_wave_add",
    "cmd_wave_edit",
    "cmd_wave_insert",
    "cmd_wave_move",
    "cmd_wave_remove",
]


@wave_app.command("add")
@render_user_errors
@serialise_plan_mutation
def cmd_wave_add(
    path: PlanPathArg,
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
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Append a new Wave at the next-available canonical id (L3+ only)."""
    from vaultspec_core.plan.commands.wave_ops import add_wave
    from vaultspec_core.plan.parser import parse_plan

    original_text = path.read_text(encoding="utf-8")
    plan = parse_plan(original_text)
    wave = add_wave(plan, title=title, intent=intent)
    save_plan_or_dry_run(
        path=path,
        plan=plan,
        original_text=original_text,
        dry_run=dry_run,
        canonicalise=canonicalise,
        success_msg=f"Added Wave `{wave.canonical_id}`.",
        json_output=json_output,
        command="vault.plan.wave.add",
    )


@wave_app.command("insert")
@render_user_errors
@serialise_plan_mutation
def cmd_wave_insert(
    path: PlanPathArg,
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
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Insert a Wave at a named position relative to an existing anchor."""
    from vaultspec_core.plan.commands.wave_ops import insert_wave
    from vaultspec_core.plan.parser import parse_plan

    original_text = path.read_text(encoding="utf-8")
    plan = parse_plan(original_text)
    wave = insert_wave(plan, title=title, intent=intent, before=before, after=after)
    save_plan_or_dry_run(
        path=path,
        plan=plan,
        original_text=original_text,
        dry_run=dry_run,
        canonicalise=canonicalise,
        success_msg=f"Inserted Wave `{wave.canonical_id}`.",
        json_output=json_output,
        command="vault.plan.wave.insert",
    )


@wave_app.command("edit")
@render_user_errors
@serialise_plan_mutation
def cmd_wave_edit(
    path: PlanPathArg,
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
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Edit the Wave's title and / or intent paragraph in place."""
    from vaultspec_core.plan.commands.wave_ops import edit_wave
    from vaultspec_core.plan.parser import parse_plan

    original_text = path.read_text(encoding="utf-8")
    plan = parse_plan(original_text)
    edit_wave(plan, wave_id, title=title, intent=intent)
    save_plan_or_dry_run(
        path=path,
        plan=plan,
        original_text=original_text,
        dry_run=dry_run,
        canonicalise=canonicalise,
        success_msg=f"Edited Wave `{wave_id}`.",
        json_output=json_output,
        command="vault.plan.wave.edit",
    )


@wave_app.command("move")
@render_user_errors
@serialise_plan_mutation
def cmd_wave_move(
    path: PlanPathArg,
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
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Re-position a Wave in document order."""
    from vaultspec_core.plan.commands.wave_ops import move_wave
    from vaultspec_core.plan.parser import parse_plan

    original_text = path.read_text(encoding="utf-8")
    plan = parse_plan(original_text)
    wave = move_wave(plan, wave_id, before=before, after=after)
    save_plan_or_dry_run(
        path=path,
        plan=plan,
        original_text=original_text,
        dry_run=dry_run,
        canonicalise=canonicalise,
        success_msg=f"Moved Wave `{wave.canonical_id}`.",
        json_output=json_output,
        command="vault.plan.wave.move",
    )


@wave_app.command("remove")
@render_user_errors
@serialise_plan_mutation
def cmd_wave_remove(
    path: PlanPathArg,
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
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Remove a Wave; descendant Phase and Step ids cascade-retire."""
    from vaultspec_core.plan.commands.wave_ops import remove_wave
    from vaultspec_core.plan.parser import parse_plan

    original_text = path.read_text(encoding="utf-8")
    plan = parse_plan(original_text)
    retired_wave, retired_phases, retired_steps = remove_wave(plan, wave_id)
    phases_str = f"{', '.join(retired_phases) if retired_phases else '(none)'}"
    steps_str = f"{', '.join(retired_steps) if retired_steps else '(none)'}"
    save_plan_or_dry_run(
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
        json_output=json_output,
        command="vault.plan.wave.remove",
    )
