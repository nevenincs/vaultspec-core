"""``vaultspec-core spec system`` - inspect and sync system prompt outputs.

Defines :data:`system_app`, mounted by :mod:`vaultspec_core.cli.spec_cmd`
onto :data:`~vaultspec_core.cli.spec_cmd_app.spec_app` as the ``system``
command group. Delegates to :mod:`vaultspec_core.core` CRUD functions via
lazy imports to avoid circular-import issues.
"""

from typing import Annotated

import typer

from vaultspec_core.cli._app import make_app
from vaultspec_core.cli._target import TargetOption, apply_target
from vaultspec_core.cli.spec_cmd_shared import (
    apply_provider_filter,
    emit_json,
    emit_sync_result,
    print_complete_sync_notice,
)

system_app = make_app(
    help="Inspect and sync assembled system prompt outputs",
    no_args_is_help=True,
)


@system_app.command("show")
def cmd_system_show(
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Display system prompt parts and targets."""
    apply_target(target)
    from vaultspec_core.core import system_show

    data = system_show()

    if json_output:
        emit_json("spec.system.show", "unchanged", data)
        raise typer.Exit(0)

    from vaultspec_core.cli.rendering import Column, render_listing, summary_line
    from vaultspec_core.console import get_console

    if not data["parts"]:
        get_console().print("[dim]No system parts found in .vaultspec/system/[/dim]")
        return

    parts_rows = [
        {
            "name": part["name"],
            "tool_filter": part["tool_filter"],
            "lines": str(part["lines"]),
        }
        for part in data["parts"]
    ]
    render_listing(
        parts_rows,
        [Column("name"), Column("tool_filter"), Column("lines")],
        title="system parts",
        summary=summary_line(len(parts_rows), "parts"),
        empty="no parts",
    )

    if data["targets"]:
        targets_rows = [
            {"tool": t["tool"], "path": t["path"], "status": f"[{t['managed']}]"}
            for t in data["targets"]
        ]
        render_listing(
            targets_rows,
            [Column("tool"), Column("path"), Column("status")],
            title="generation targets",
            summary=summary_line(len(targets_rows), "targets"),
            empty="no targets",
        )


@system_app.command("sync")
def cmd_system_sync(
    provider: Annotated[
        str,
        typer.Argument(
            help="Provider to sync (all, claude, gemini, antigravity, codex)"
        ),
    ] = "all",
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview changes")] = False,
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite non-managed files")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Sync only system prompts; use vaultspec-core sync for complete refresh."""
    apply_target(target)
    apply_provider_filter(provider)
    from vaultspec_core.core import system_sync

    result = system_sync(dry_run=dry_run, force=force)

    if not json_output:
        print_complete_sync_notice(resource="system prompt")
    emit_sync_result(result, label="System", dry_run=dry_run, json_output=json_output)
