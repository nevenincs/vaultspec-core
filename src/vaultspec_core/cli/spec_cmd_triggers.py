"""``vaultspec-core spec triggers`` - author and run vaultspec lifecycle triggers.

Defines :data:`triggers_app`, mounted by :mod:`vaultspec_core.cli.spec_cmd`
onto :data:`~vaultspec_core.cli.spec_cmd_app.spec_app`. A trigger binds a
vaultspec lifecycle event to a shell command, gated on the operator consent
ledger in :mod:`vaultspec_core.triggers.trust`.

Distinct from :mod:`.spec_cmd_hooks`, which is the agent-runtime hooks each
provider runs, and from :mod:`.spec_cmd_git`, which is the git pre-commit
boundary. This group was reached as ``spec hooks`` before those three were
separated. Delegates to :mod:`vaultspec_core.core` CRUD functions via lazy
imports to avoid circular-import issues.
"""

from pathlib import Path
from typing import Annotated

import typer

from vaultspec_core.cli._app import make_app
from vaultspec_core.cli._errors import handle_error as _handle_error
from vaultspec_core.cli._target import TargetOption, apply_target
from vaultspec_core.cli.spec_cmd_shared import (
    emit_json,
    print_source_mutation_notice,
)

triggers_app = make_app(
    help="Author and run shell commands bound to vaultspec lifecycle events",
    no_args_is_help=True,
)


@triggers_app.command("list")
def cmd_triggers_list(
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """List this workspace's lifecycle triggers."""
    apply_target(target)
    from vaultspec_core.core.commands import triggers_list_data

    data = triggers_list_data()

    if json_output:
        emit_json("spec.triggers.list", "unchanged", data)
        raise typer.Exit(0)

    from vaultspec_core.cli.rendering import Cell, Column, render_listing, summary_line
    from vaultspec_core.console import get_console

    triggers = data["triggers"]
    console = get_console()

    if not triggers:
        console.print("No triggers defined.")
        console.print(
            f"  Add [dim].yaml[/dim] files to [bold]{data['triggers_dir']}/[/bold]"
        )
        console.print(
            "\n[dim]Supported events:[/dim] " + ", ".join(data["supported_events"])
        )
        return

    rows = [
        {
            "name": trig["name"],
            "status": Cell("enabled", style="bold green")
            if trig["enabled"]
            else Cell("disabled", style="dim"),
            "trust": Cell("trusted", style="bold green")
            if trig["trusted"]
            else Cell("untrusted", style="yellow"),
            "event": trig["event"],
            "actions": trig["actions"],
        }
        for trig in triggers
    ]
    render_listing(
        rows,
        [
            Column("name"),
            Column("status"),
            Column("trust"),
            Column("event"),
            Column("actions"),
        ],
        title="hooks",
        summary=summary_line(len(rows), "hooks"),
        empty="no triggers",
    )
    if any(not trig["trusted"] for trig in triggers):
        console.print(
            "\n[dim]Untrusted hooks are never run. Their commands would "
            "execute as you, and a repository cannot approve its own; review "
            "them, then run[/dim] [bold]vaultspec-core spec hooks trust[/bold]."
        )


@triggers_app.command("add")
def cmd_triggers_add(
    name: Annotated[str, typer.Argument(help="Trigger name")],
    event: Annotated[
        str, typer.Option("--event", help="Lifecycle event to trigger on")
    ] = "config.synced",
    command: Annotated[str, typer.Option("--command", help="Command to run")] = "",
    body: Annotated[
        str | None, typer.Option("--body", help="Trigger body content")
    ] = None,
    from_file: Annotated[
        Path | None, typer.Option("--from-file", help="Read body content from file")
    ] = None,
    force: Annotated[bool, typer.Option("--force", help="Overwrite existing")] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Preview without writing")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Add a new lifecycle trigger under .vaultspec/triggers/."""
    apply_target(target)

    if from_file and body is not None:
        typer.echo("Error: Cannot specify both --body and --from-file.", err=True)
        raise typer.Exit(code=1)

    resolved_body = None
    if from_file:
        if not from_file.exists():
            typer.echo(f"Error: File not found: {from_file}", err=True)
            raise typer.Exit(code=1)
        resolved_body = from_file.read_text(encoding="utf-8")
    elif body is not None:
        resolved_body = body

    from vaultspec_core.core import triggers_add
    from vaultspec_core.core.exceptions import VaultSpecError

    try:
        file_path = triggers_add(
            name=name,
            event=event,
            command=command,
            force=force,
            body=resolved_body,
            dry_run=dry_run,
        )
    except VaultSpecError as exc:
        _handle_error(exc, json_output=json_output)
        return

    if json_output:
        emit_json("spec.triggers.add", "created", {"path": str(file_path)})
        raise typer.Exit(0)

    action = "Would create hook source" if dry_run else "Trigger source updated"
    print_source_mutation_notice(file_path, action=action)


@triggers_app.command("show")
def cmd_triggers_show(
    name: Annotated[str, typer.Argument(help="Trigger name")],
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Display a trigger's source file."""
    apply_target(target)
    from vaultspec_core.core import triggers_show
    from vaultspec_core.core.exceptions import VaultSpecError

    try:
        content = triggers_show(name=name)
        if json_output:
            emit_json(
                "spec.triggers.show", "unchanged", {"name": name, "content": content}
            )
            raise typer.Exit(0)
        typer.echo(content)
    except (VaultSpecError, OSError) as exc:
        _handle_error(exc, json_output=json_output)


@triggers_app.command("edit")
def cmd_triggers_edit(
    name: Annotated[str, typer.Argument(help="Trigger name")],
    editor: Annotated[
        str | None,
        typer.Option(
            "--editor",
            help=(
                "Override the editor for this invocation. Must name a known "
                "editor program; arguments are allowed (e.g. 'code --wait'). "
                "For an editor outside that set, use VAULTSPEC_EDITOR."
            ),
        ),
    ] = None,
    target: TargetOption = None,
) -> None:
    """Open a trigger in the configured editor."""
    apply_target(target)
    from vaultspec_core.core import triggers_edit
    from vaultspec_core.core.exceptions import (
        EditorCancellationError,
        EditorResolutionError,
        EditorSubprocessError,
        VaultSpecError,
    )

    try:
        triggers_edit(name=name, editor=editor)
    except EditorResolutionError as exc:
        typer.echo(f"Error: {exc}", err=True)
        if exc.hint:
            typer.echo(f"  Hint: {exc.hint}", err=True)
        raise typer.Exit(code=2) from exc
    except EditorSubprocessError as exc:
        typer.echo(f"Error: {exc}", err=True)
        if exc.hint:
            typer.echo(f"  Hint: {exc.hint}", err=True)
        raise typer.Exit(code=3) from exc
    except EditorCancellationError as exc:
        typer.echo(f"Error: {exc}", err=True)
        if exc.hint:
            typer.echo(f"  Hint: {exc.hint}", err=True)
        raise typer.Exit(code=4) from exc
    except VaultSpecError as exc:
        _handle_error(exc)
    except OSError as exc:
        _handle_error(exc)


@triggers_app.command("rename")
def cmd_triggers_rename(
    old_name: Annotated[str, typer.Argument(help="Current hook name")],
    new_name: Annotated[str, typer.Argument(help="New hook name")],
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Rename an existing trigger atomically."""
    apply_target(target)
    from vaultspec_core.core import triggers_rename
    from vaultspec_core.core.exceptions import VaultSpecError

    try:
        new_path = triggers_rename(old_name=old_name, new_name=new_name)
    except (VaultSpecError, OSError) as exc:
        _handle_error(exc, json_output=json_output)
        return

    if json_output:
        emit_json(
            "spec.triggers.rename",
            "updated",
            {"old_name": old_name, "new_name": new_name, "path": str(new_path)},
        )
        raise typer.Exit(0)

    print_source_mutation_notice(new_path, action="Trigger source renamed")


@triggers_app.command("remove")
def cmd_triggers_remove(
    name: Annotated[str, typer.Argument(help="Trigger name")],
    force: Annotated[
        bool,
        typer.Option(
            "--yes",
            "-y",
            "--force",
            help="Confirm removal without prompting",
        ),
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Delete a trigger."""
    apply_target(target)
    from vaultspec_core.core import triggers_remove
    from vaultspec_core.core.exceptions import VaultSpecError

    try:
        triggers_remove(
            name=name,
            force=force,
            confirm_fn=typer.confirm,
        )
    except (VaultSpecError, OSError) as exc:
        _handle_error(exc, json_output=json_output)
        return

    if json_output:
        emit_json("spec.triggers.remove", "removed", {"removed": name})
        raise typer.Exit(0)

    from vaultspec_core.core.triggers import resolve_trigger_path

    print_source_mutation_notice(
        resolve_trigger_path(name),
        action="Trigger source removed",
    )


@triggers_app.command("status")
def cmd_triggers_status(
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Report trigger parse errors and unsupported events."""
    apply_target(target)
    from vaultspec_core.core import triggers_status

    status = triggers_status()

    if json_output:
        emit_json("spec.triggers.status", status["status"], status)
        raise typer.Exit(0 if status["status"] == "ok" else 1)

    from vaultspec_core.cli.rendering import Field, render_record
    from vaultspec_core.console import get_console

    status_str = str(status["status"])
    status_style = (
        "green"
        if status_str == "ok"
        else ("yellow" if status_str == "warning" else "red")
    )
    fields = [
        Field("status", status_str, style=status_style),
        Field("triggers_dir", str(status["triggers_dir"])),
        Field("definitions", ", ".join(status["definitions"]) or "none"),
    ]
    render_record(fields, title="hooks status")

    console = get_console()
    for warning in status["warnings"]:
        console.print(f"  [yellow]-[/yellow] {warning}")
    for error in status["errors"]:
        console.print(f"  [red]-[/red] {error}")
    if status["status"] != "ok":
        raise typer.Exit(code=1)


@triggers_app.command("run")
def cmd_triggers_run(
    event: Annotated[str, typer.Argument(help="Event name")],
    path: Annotated[
        str | None, typer.Option("--path", help="Context path variable")
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Fire this workspace's triggers for one lifecycle event."""
    apply_target(target)
    from vaultspec_core.cli._trigger_trust import consent_gate
    from vaultspec_core.console import get_console
    from vaultspec_core.core.commands import triggers_run
    from vaultspec_core.core.exceptions import VaultSpecError

    consent_gate(event, json_output=json_output)

    try:
        results = triggers_run(event=event, path=path)
    except VaultSpecError as exc:
        _handle_error(exc, json_output=json_output)
        return

    if json_output:
        emit_json("spec.triggers.run", "unchanged", {"results": results})
        raise typer.Exit(0)

    console = get_console()
    if not results:
        console.print(f"[dim]No enabled hooks for event: {event}[/dim]")
        return

    for r in results:
        if r["success"]:
            icon = "[bold green]OK[/bold green]"
        else:
            icon = "[bold red]FAIL[/bold red]"
        console.print(f"  {r['trigger_name']} ({r['action_type']}): {icon}")
        if r["output"]:
            for line in str(r["output"]).splitlines()[:5]:
                console.print(f"    {line}")
        if r["error"]:
            console.print(f"    [red]error:[/red] {r['error']}")


@triggers_app.command("trust")
def cmd_triggers_trust(
    name: Annotated[
        str | None,
        typer.Argument(help="Trigger name; omit to cover every hook in the workspace"),
    ] = None,
    revoke: Annotated[
        bool,
        typer.Option(
            "--revoke", help="Withdraw approval for this workspace's triggers"
        ),
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Approve this workspace's triggers to run their shell commands as you.

    Trigger files are shared through git, so a checkout arrives carrying commands
    its author chose. Approval is therefore recorded on this machine rather than
    in the workspace, and is pinned to each file's current contents: editing an
    approved trigger, or pulling a change to one, withdraws the approval until you
    run this again. Use --revoke to withdraw it yourself.
    """
    apply_target(target)
    from vaultspec_core.cli._trigger_trust import describe_trigger
    from vaultspec_core.core.exceptions import ResourceNotFoundError
    from vaultspec_core.core.types import get_context
    from vaultspec_core.triggers import grant, load_triggers
    from vaultspec_core.triggers import revoke as revoke_trust

    ctx = get_context()

    if revoke:
        dropped = revoke_trust(ctx.triggers_dir)
        if json_output:
            emit_json("spec.triggers.trust", "removed", {"revoked": dropped})
            raise typer.Exit(0)
        from vaultspec_core.console import get_console

        get_console().print(f"Withdrew approval for {dropped} trigger(s).")
        return

    triggers = load_triggers(ctx.triggers_dir)
    if name is not None:
        triggers = [trig for trig in triggers if trig.name == name]
        if not triggers:
            _handle_error(
                ResourceNotFoundError(f"Trigger '{name}' not found."),
                json_output=json_output,
            )
            return

    paths = [t.source_path for t in triggers if t.source_path is not None]
    recorded = grant(paths)
    approved = sorted(path.name for path in recorded)

    if json_output:
        emit_json("spec.triggers.trust", "updated", {"trusted": approved})
        raise typer.Exit(0)

    from vaultspec_core.console import get_console

    console = get_console()
    if not approved:
        console.print("No triggers to approve.")
        return
    console.print(f"Approved {len(approved)} trigger(s) in {ctx.triggers_dir}:")
    # Echo the commands that were just approved rather than only the filenames.
    # This verb is the one place an operator commits to running them, so it is
    # the one place the record of what they agreed to has to be legible.
    for trig in triggers:
        if trig.source_path is None or trig.source_path not in recorded:
            continue
        for line in describe_trigger(trig, ctx.target_dir):
            console.print(line, highlight=False)
    console.print(
        "[dim]Approval is recorded on this machine and pinned to each file's "
        "contents; editing a trigger asks again.[/dim]"
    )
