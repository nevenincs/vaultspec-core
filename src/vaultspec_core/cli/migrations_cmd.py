"""CLI surface for the schema migration registry.

Exposes ``vaultspec-core migrations status`` (read-only) and
``vaultspec-core migrations run`` (explicit trigger). Both commands
operate on the workspace selected by the global ``--target`` option.
"""

from __future__ import annotations

import json as _json
import logging
from typing import Annotated

import typer

from vaultspec_core.cli._target import TargetOption, apply_target

logger = logging.getLogger(__name__)

migrations_app = typer.Typer(
    help="Inspect and run vaultspec-core schema migrations.",
    no_args_is_help=True,
    add_completion=False,
)


@migrations_app.command("status")
def cmd_migrations_status(
    target: TargetOption = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Show registered migrations and which entries are pending.

    Reads the workspace manifest's ``vaultspec_version`` and lists
    every registered migration plus the subset whose ``target_version``
    exceeds it. Read-only; never mutates the workspace.

    Exit codes: ``0`` when the workspace is up to date or has no
    manifest, ``1`` when migrations are pending.

    Examples:\n
      vaultspec-core migrations status\n
      vaultspec-core migrations status --json\n
    """
    apply_target(target)

    from vaultspec_core.core.manifest import read_manifest_data
    from vaultspec_core.core.types import get_context
    from vaultspec_core.migrations import (
        REGISTRY,
        MigrationStatus,
        list_pending,
        migration_status,
    )

    root_dir = get_context().target_dir
    mdata = read_manifest_data(root_dir)
    manifest_version = mdata.vaultspec_version
    status, _pending_names = migration_status(root_dir, manifest=mdata)

    pending = list_pending(root_dir, manifest=mdata)

    if json_output:
        payload = {
            "manifest_version": manifest_version,
            "status": status.value,
            "registered": [
                {"name": m.name, "target_version": m.target_version} for m in REGISTRY
            ],
            "pending": [
                {"name": m.name, "target_version": m.target_version} for m in pending
            ],
        }
        typer.echo(_json.dumps(payload, indent=2))
        raise typer.Exit(code=0 if status != MigrationStatus.PENDING else 1)

    from vaultspec_core.console import get_console

    console = get_console()
    console.print(f"[bold]migration status[/bold]: {status.value}")
    console.print(f"  manifest version: {manifest_version or '(unset)'}")
    console.print(f"  registered: {len(REGISTRY)}")
    for m in REGISTRY:
        marker = (
            "[yellow]pending[/yellow]" if m in pending else "[green]applied[/green]"
        )
        console.print(f"    {marker} {m.target_version}  {m.name}")
    if status == MigrationStatus.PENDING:
        console.print()
        console.print(
            "  Run [bold]vaultspec-core migrations run[/bold] to apply pending entries."
        )
        raise typer.Exit(code=1)
    raise typer.Exit(code=0)


@migrations_app.command("run")
def cmd_migrations_run(
    target: TargetOption = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Run pending schema migrations and bump the manifest version.

    Executes every registered migration whose ``target_version``
    exceeds the manifest's ``vaultspec_version``. On success bumps
    ``vaultspec_version`` to the running package version. A migration
    that raises stops the run and leaves the manifest unchanged so the
    next invocation re-attempts.

    Exit codes: ``0`` on success (including the no-pending no-op),
    ``1`` if any migration raised.

    Examples:\n
      vaultspec-core migrations run\n
      vaultspec-core migrations run --json\n
    """
    apply_target(target)

    from vaultspec_core.core.types import get_context
    from vaultspec_core.migrations import run_pending_migrations

    root_dir = get_context().target_dir

    try:
        results = run_pending_migrations(root_dir)
    except Exception as exc:
        if json_output:
            typer.echo(_json.dumps({"ok": False, "error": str(exc)}, indent=2))
        else:
            typer.echo(f"Error: migration failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if json_output:
        typer.echo(
            _json.dumps(
                {
                    "ok": True,
                    "applied": [
                        {
                            "name": r.name,
                            "target_version": r.target_version,
                            "summary": r.summary,
                            "counts": r.counts,
                        }
                        for r in results
                    ],
                },
                indent=2,
            )
        )
        raise typer.Exit(code=0)

    from vaultspec_core.console import get_console

    console = get_console()
    if not results:
        console.print("[green]up to date[/green]: no pending migrations.")
    else:
        console.print(
            f"[bold]Applied {len(results)} migration"
            f"{'s' if len(results) != 1 else ''}.[/bold]"
        )
        for r in results:
            console.print(
                f"  [green]ok[/green] {r.target_version}  {r.name}: {r.summary}"
            )
    raise typer.Exit(code=0)
