"""Epic-intent ``vault plan epic intent`` commands (L4 plans only): show / edit.

Defines :data:`epic_intent_app` and mounts it onto
:data:`vaultspec_core.cli.plan_cmd_app.epic_app` as ``intent``. Split out of
:mod:`vaultspec_core.cli.plan_cmd` along the Epic container seam.
"""

from typing import Annotated

import typer

from vaultspec_core.cli._app import make_app
from vaultspec_core.cli._target import PlanPathArg
from vaultspec_core.cli.plan_cmd_app import epic_app
from vaultspec_core.cli.plan_cmd_shared import (
    render_user_errors,
    save_plan_or_dry_run,
)

__all__ = ["cmd_epic_intent_edit", "cmd_epic_intent_show", "epic_intent_app"]

epic_intent_app = make_app(
    help="Show or edit the L4 plan's Epic intent paragraph",
    no_args_is_help=True,
)
epic_app.add_typer(epic_intent_app, name="intent")


@epic_intent_app.command("show")
def cmd_epic_intent_show(
    path: PlanPathArg,
) -> None:
    """Print the Epic intent paragraph (L4 plans only)."""
    from vaultspec_core.plan.commands.epic_ops import show_epic_intent
    from vaultspec_core.plan.parser import parse_plan

    plan = parse_plan(path)
    typer.echo(show_epic_intent(plan))


@epic_intent_app.command("edit")
@render_user_errors
def cmd_epic_intent_edit(
    path: PlanPathArg,
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
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Replace the Epic intent paragraph (L4 plans only)."""
    from vaultspec_core.plan.commands.epic_ops import edit_epic_intent
    from vaultspec_core.plan.parser import parse_plan

    original_text = path.read_text(encoding="utf-8")
    plan = parse_plan(original_text)
    edit_epic_intent(plan, text=text)
    save_plan_or_dry_run(
        path=path,
        plan=plan,
        original_text=original_text,
        dry_run=dry_run,
        canonicalise=canonicalise,
        success_msg="Edited Epic intent.",
        json_output=json_output,
        command="vault.plan.epic.intent.edit",
    )
