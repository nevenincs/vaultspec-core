"""Typer wiring for explicit execution-record recovery commands.

The ``vault exec`` group deliberately owns one-record-at-a-time recovery of
historical ``step_id`` mappings.  It delegates all validation and writes to
``vaultcore.exec_recovery``; these wrappers only resolve the active target,
render the shared command contract, and invalidate the graph cache after a
real change.
"""

from __future__ import annotations

import json
from pathlib import Path  # noqa: TC003 - Typer inspects this command annotation.
from typing import Annotated

import typer

from vaultspec_core.cli._app import make_app
from vaultspec_core.cli._errors import handle_error
from vaultspec_core.cli._target import TargetOption, apply_target

__all__ = ["exec_app"]


exec_app = make_app(
    help="Recover historical execution-record Step mappings explicitly",
    no_args_is_help=True,
)


def _record_path(root_dir: Path, record: Path) -> Path:
    """Resolve a record path relative to the active vault root.

    A caller may pass either a repository-relative path or an absolute path.
    The recovery layer verifies that the resulting path is a live execution
    record, so this helper intentionally performs no stem lookup or fallback
    search that could select the wrong historical evidence.
    """
    return record if record.is_absolute() else root_dir / record


def _emit_result(
    result: object,
    *,
    root_dir: Path,
    dry_run: bool,
    json_output: bool,
) -> None:
    """Render one recovery result through text and JSON contracts."""
    from vaultspec_core.console import get_console
    from vaultspec_core.vaultcore.exec_recovery import ExecRecoveryResult

    assert isinstance(result, ExecRecoveryResult)
    command = f"vault.exec.{result.operation}"
    changed = result.operation == "retire" or result.previous_step_id != result.step_id

    def display(path: Path) -> str:
        try:
            return str(path.relative_to(root_dir))
        except ValueError:
            return str(path)

    payload: dict[str, object] = {
        "record": display(result.record_path),
        "previous_step_id": result.previous_step_id,
        "step_id": result.step_id,
        "dry_run": dry_run,
        "changed": changed,
    }
    if result.archive_path is not None:
        payload["archive_path"] = display(result.archive_path)

    if json_output:
        from vaultspec_core.cli.rendering import json_envelope

        typer.echo(json.dumps(json_envelope(command, result.status, payload), indent=2))
        return

    console = get_console()
    if not changed:
        console.print(f"[dim]Unchanged:[/dim] {display(result.record_path)}")
        return
    if dry_run:
        console.print(
            f"[dim]Would {result.operation}:[/dim] {display(result.record_path)}"
        )
        return
    if result.archive_path is not None:
        console.print(
            f"[yellow]Retired:[/yellow] {display(result.record_path)} -> "
            f"{display(result.archive_path)}"
        )
        return
    console.print(
        f"[yellow]{result.operation.capitalize()}ed:[/yellow] "
        f"{display(result.record_path)}"
    )


def _run_recovery(
    operation: str,
    *,
    record: Path,
    target_step: str | None,
    dry_run: bool,
    json_output: bool,
    target: Path | None,
) -> None:
    """Resolve the workspace and dispatch one typed recovery operation."""
    apply_target(target, json_output=json_output)
    from vaultspec_core.cli._cache_hook import invalidate_graph_cache
    from vaultspec_core.core.types import get_context
    from vaultspec_core.vaultcore.exec_recovery import (
        detach_exec_record,
        relink_exec_record,
        retire_exec_record,
    )

    root_dir = get_context().target_dir
    record_path = _record_path(root_dir, record)
    try:
        if operation == "relink":
            assert target_step is not None
            result = relink_exec_record(
                root_dir, record_path, target_step, dry_run=dry_run
            )
        elif operation == "retire":
            result = retire_exec_record(root_dir, record_path, dry_run=dry_run)
        else:
            result = detach_exec_record(root_dir, record_path, dry_run=dry_run)
    except Exception as exc:
        handle_error(exc, json_output=json_output)
        return

    _emit_result(result, root_dir=root_dir, dry_run=dry_run, json_output=json_output)
    if result.status == "updated" and not dry_run:
        invalidate_graph_cache(root_dir)


@exec_app.command("relink")
def cmd_exec_relink(
    record: Annotated[
        Path,
        typer.Option("--record", help="Live execution-record path"),
    ],
    step: Annotated[
        str,
        typer.Option(
            "--step", help="Live Step identifier or display path in its parent plan"
        ),
    ],
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Preview the recovery without writing")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Relink one execution record to a live Step in its existing parent plan."""
    _run_recovery(
        "relink",
        record=record,
        target_step=step,
        dry_run=dry_run,
        json_output=json_output,
        target=target,
    )


@exec_app.command("retire")
def cmd_exec_retire(
    record: Annotated[
        Path,
        typer.Option("--record", help="Live execution-record path"),
    ],
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Preview the recovery without writing")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Archive one record only when its current Step is retired by its parent plan."""
    _run_recovery(
        "retire",
        record=record,
        target_step=None,
        dry_run=dry_run,
        json_output=json_output,
        target=target,
    )


@exec_app.command("detach")
def cmd_exec_detach(
    record: Annotated[
        Path,
        typer.Option("--record", help="Live execution-record path"),
    ],
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Preview the recovery without writing")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Remove a Step claim only when it resolves to neither a live nor retired Step."""
    _run_recovery(
        "detach",
        record=record,
        target_step=None,
        dry_run=dry_run,
        json_output=json_output,
        target=target,
    )
