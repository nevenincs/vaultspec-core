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
from vaultspec_core.cli.json_output import json_format_kwargs

__all__ = ["exec_app"]


exec_app = make_app(
    help="Write the execution ledger and recover historical Step mappings",
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

        typer.echo(
            json.dumps(
                json_envelope(command, result.status, payload), **json_format_kwargs()
            )
        )
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


@exec_app.command("log")
def cmd_exec_log(
    feature: Annotated[
        str, typer.Option("--feature", help="Feature tag (with or without '#')")
    ],
    related: Annotated[
        str, typer.Option("--related", help="Parent plan stem this ledger records")
    ],
    step: Annotated[
        str,
        typer.Option("--step", help="Canonical Step ID or display path being logged"),
    ],
    row: Annotated[
        list[str] | None,
        typer.Option(
            "--row",
            help=(
                "Row to append as 'OP:path' (A added, M modified, D deleted) "
                "or 'R:old->new'; repeatable"
            ),
        ),
    ] = None,
    verify: Annotated[
        str | None,
        typer.Option(
            "--verify",
            help="Check that was run, as '<command>=pass' or '<command>=fail'",
        ),
    ] = None,
    by: Annotated[
        str | None,
        typer.Option("--by", help="Persona that closed the Step, e.g. a worker name"),
    ] = None,
    note: Annotated[
        list[str] | None,
        typer.Option(
            "--note",
            help=(
                "Exception note (data loss, skipped work, a scaffold left in code, "
                "a persistent failure); repeatable"
            ),
        ),
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Preview without writing")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Append a Step's rows to its plan's ledger.

    Creates the ledger on first use, so an executor logging its first Step
    never has to know whether the document exists yet. The ledger is
    append-only: existing rows are never rewritten, and re-logging the same
    row is idempotent rather than duplicating it. ``--verify`` and ``--by``
    add one row each; ``--note`` adds a ``## Notes`` line under the Step id.
    """
    apply_target(target, json_output=json_output)
    from vaultspec_core.cli import _add_ops
    from vaultspec_core.cli._cache_hook import invalidate_graph_cache
    from vaultspec_core.console import get_console
    from vaultspec_core.core.types import get_context as _get_ctx

    console = get_console()
    root_dir = _get_ctx().root_dir
    rows = _add_ops.parse_row_specs(console, row or [])
    verify_pair = _add_ops.parse_verify(console, verify)

    try:
        outcome = _add_ops.log_ledger_rows(
            console,
            root_dir=root_dir,
            feature=feature,
            plan_stem=related,
            step=step,
            rows=rows,
            verify=verify_pair,
            by=by,
            notes=note or [],
            dry_run=dry_run,
            json_output=json_output,
        )
    except typer.Exit:
        raise
    except Exception as exc:
        handle_error(exc, json_output=json_output)
        return

    if not dry_run and outcome.changed:
        invalidate_graph_cache(root_dir)
    if json_output:
        from vaultspec_core.cli.rendering import json_envelope

        payload: dict[str, object] = {
            "path": str(outcome.path),
            "step": outcome.step_id,
            "rows": len(outcome.rows),
            "notes": len(outcome.notes),
            "changed": outcome.changed,
        }
        if dry_run:
            payload["dry_run"] = True
        typer.echo(
            json.dumps(json_envelope("vault.exec.log", "logged", payload), indent=2)
        )


@exec_app.command("fold")
def cmd_exec_fold(
    feature: Annotated[
        str, typer.Option("--feature", help="Feature tag (with or without '#')")
    ],
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Report the fold plan without writing")
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", help="Required to apply; the fold removes records"),
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Fold a feature's per-Step execution records into its plan's ledger.

    A ``body-v1`` record's ``## Scope`` paths become ``T`` (touched) rows,
    because that schema never recorded an operation and none is invented. A
    ``body-v2`` record's ``## Changes`` rows fold with their operations and
    ``verify:`` line intact, and its ``## Notes`` lines are carried under the
    Step id. A Phase Summary is removed once every Step of its Phase has rows.
    Other prose is discarded and is recoverable from the commit preceding the
    fold.

    Destructive, so it refuses to write without ``--force`` and reports the
    plan instead.
    """
    apply_target(target, json_output=json_output)
    from vaultspec_core.cli import _add_ops
    from vaultspec_core.cli._cache_hook import invalidate_graph_cache
    from vaultspec_core.console import get_console
    from vaultspec_core.core.types import get_context as _get_ctx

    console = get_console()
    root_dir = _get_ctx().root_dir

    try:
        ledger_path, plan = _add_ops.fold_exec_records(
            console,
            root_dir=root_dir,
            feature=feature,
            dry_run=dry_run,
            force=force,
            json_output=json_output,
        )
    except typer.Exit:
        raise
    except Exception as exc:
        handle_error(exc, json_output=json_output)
        return

    if not dry_run and ledger_path is not None:
        invalidate_graph_cache(root_dir)
    if json_output:
        from vaultspec_core.cli.rendering import json_envelope

        payload: dict[str, object] = {
            "path": str(ledger_path) if ledger_path else None,
            "folded": len(getattr(plan, "folded", [])),
            "summaries_removed": len(getattr(plan, "summaries", [])),
            "rows": len(getattr(plan, "rows", [])),
            "notes": len(getattr(plan, "notes", [])),
            "recovered_paths": getattr(plan, "recovered_paths", 0),
            "skipped": len(getattr(plan, "skipped", [])),
        }
        if dry_run:
            payload["dry_run"] = True
        typer.echo(
            json.dumps(json_envelope("vault.exec.fold", "folded", payload), indent=2)
        )
