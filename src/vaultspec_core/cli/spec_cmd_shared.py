"""Shared helpers for the ``spec`` command group's resource sub-apps.

Provides the JSON envelope, sync-result rendering, provider filtering, and
restore/status/editor plumbing shared by the rules, skills, agents, hooks,
and mcps command modules under :mod:`vaultspec_core.cli`. Kept separate
from :mod:`vaultspec_core.cli.spec_cmd` so each resource module can import
just this shared surface without pulling in the doctor and reference
command modules too.
"""

from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING

import typer

if TYPE_CHECKING:
    from vaultspec_core.core.types import SyncResult

from vaultspec_core.cli._errors import handle_error as _handle_error

__all__ = [
    "COMPLETE_SYNC_COMMAND",
    "PROVIDER_OUTPUTS",
    "_apply_provider_filter",
    "_emit_json",
    "_emit_sync_result",
    "_print_complete_sync_notice",
    "_print_source_mutation_notice",
    "_resource_path",
    "_restore_resource_command",
    "_run_edit_command",
    "_spec_status_command",
]

COMPLETE_SYNC_COMMAND = "vaultspec-core sync"
PROVIDER_OUTPUTS = (
    "AGENTS.md, CLAUDE.md, GEMINI.md, native MCP configs, and provider directories"
)


def _print_complete_sync_notice(*, resource: str, mcp: bool = False) -> None:
    """Note, as a quiet footnote, that this is a scoped sync.

    Rendered dim rather than yellow: it is informational guidance toward
    the complete-refresh path, not a warning, so it should not read as an
    alarm on every invocation.
    """
    from vaultspec_core.console import get_console

    scope = "native MCP targets only" if mcp else f"{resource} resource files only"
    get_console().print(
        f"[dim]Scoped sync: {scope}. Run [bold]{COMPLETE_SYNC_COMMAND}[/bold] "
        f"for the full provider refresh.[/dim]"
    )


def _emit_sync_result(
    result: "SyncResult",
    *,
    label: str,
    dry_run: bool,
    json_output: bool,
    command: str | None = None,
) -> None:
    """Render a sync pass through the canonical outcome renderer.

    Routes the text summary and the ``--json`` payload through one
    :class:`~vaultspec_core.cli.rendering.OutcomeItem` list, per the
    ``cli-sync-vocabulary`` ADR, so the two surfaces cannot drift apart.
    Always raises :class:`typer.Exit` - code 1 when the pass recorded a
    failure, else 0.
    """
    from vaultspec_core.cli.rendering import OutcomeItem, emit_outcomes, sync_outcomes

    outcomes: list[OutcomeItem] = []
    if result.per_tool:
        for provider, provider_result in result.per_tool.items():
            outcomes.extend(sync_outcomes(provider_result, group=provider))
    else:
        outcomes = sync_outcomes(result)
    title = f"{label} sync" + (" (dry run)" if dry_run else "")
    extra = {"warnings": result.warnings} if result.warnings else None
    code = emit_outcomes(
        outcomes,
        command=command or f"spec.{label.lower()}.sync",
        title=title,
        json_output=json_output,
        extra_json=extra,
    )

    if result.warnings and not json_output:
        from vaultspec_core.console import get_console

        console = get_console()
        for warning in result.warnings:
            console.print(f"  [yellow]-[/yellow] {warning}")

    raise typer.Exit(code)


def _apply_provider_filter(provider: str) -> None:
    """Validate provider is installed and filter tool_configs in active context."""
    from dataclasses import replace

    import typer

    from vaultspec_core.core.commands import SYNC_PROVIDERS
    from vaultspec_core.core.manifest import read_manifest
    from vaultspec_core.core.types import Tool, get_context, set_context

    if provider not in SYNC_PROVIDERS:
        typer.echo(
            f"Error: Unknown sync target '{provider}'. "
            f"Valid: {', '.join(sorted(SYNC_PROVIDERS))}",
            err=True,
        )
        raise typer.Exit(code=1)

    if provider == "all":
        return

    ctx = get_context()
    root_dir = ctx.target_dir

    installed = read_manifest(root_dir)
    if installed and provider not in installed:
        typer.echo(
            f"Error: Provider '{provider}' is not installed.\n"
            f"  Hint: Run 'vaultspec-core install "
            f"--target {root_dir} {provider}' first.",
            err=True,
        )
        raise typer.Exit(code=1)

    # Reuse the single provider-to-tool map rather than re-deriving it here, so
    # the CLI filter cannot drift from the install/sync mapping. "all" is handled
    # by the early return above; "core" never reaches here (not in SYNC_PROVIDERS).
    from vaultspec_core.core.commands import _PROVIDER_TO_TOOLS

    requested: set[Tool] = set(_PROVIDER_TO_TOOLS.get(provider, []))

    narrowed = {k: v for k, v in ctx.tool_configs.items() if k in requested}
    set_context(replace(ctx, tool_configs=narrowed))


def _print_source_mutation_notice(path: Path, *, action: str) -> None:
    """Explain that source-side resource changes need top-level sync."""
    from vaultspec_core.console import get_console

    console = get_console()
    console.print(f"{action}: {path}")
    console.print(
        "[yellow]Provider-facing outputs were not updated.[/yellow] "
        f"Run [bold]{COMPLETE_SYNC_COMMAND}[/bold] to refresh {PROVIDER_OUTPUTS} "
        "where applicable."
    )


def _resource_path(base_dir: Path, name: str, *, suffix: str = ".md") -> Path:
    filename = name if name.endswith(suffix) else f"{name}{suffix}"
    return base_dir / filename


def _emit_json(command: str, status: str, data: Mapping[str, object]) -> None:
    """Print a command payload as the canonical ``--json`` envelope.

    Per the ``cli-json-consistency`` ADR every ``--json`` output shares
    the ``{schema, status, data}`` shape.
    """
    import json

    from vaultspec_core.cli.rendering import json_envelope

    typer.echo(json.dumps(json_envelope(command, status, data), indent=2, default=str))


def _restore_resource_command(
    *,
    category: str,
    label: str,
    filename: str,
    json_output: bool,
) -> None:
    """Shared body for ``spec {rules,skills,agents} restore``.

    Bare-name resolution to the canonical ``.builtin.md`` form is handled
    by :func:`~vaultspec_core.core.revert.revert_resource`. Always raises
    :class:`typer.Exit` - code 0 on success, 1 on failure - and honours
    ``--json`` on both paths.
    """
    from vaultspec_core.core.revert import revert_resource
    from vaultspec_core.core.types import get_context

    vaultspec_dir = get_context().target_dir / ".vaultspec"
    result = revert_resource(vaultspec_dir, category, filename)
    reverted = bool(result.get("reverted"))
    resolved = str(result.get("filename", filename))
    reason = str(result.get("reason", "restore failed"))

    if json_output:
        if reverted:
            _emit_json(f"spec.{category}.restore", "restored", {"name": resolved})
        else:
            _emit_json(f"spec.{category}.restore", "failed", {"message": reason})
        raise typer.Exit(0 if reverted else 1)

    if reverted:
        typer.echo(f"Restored {label}: {resolved}")
        raise typer.Exit(0)
    typer.echo(reason, err=True)
    raise typer.Exit(code=1)


def _spec_status_command(result: "SyncResult", label: str, json_output: bool) -> None:
    missing: list[str] = []
    drifted: list[str] = []
    stale: list[str] = []
    up_to_date: list[str] = []
    skipped: list[str] = []
    for path, action in result.items:
        if action == "[ADD]":
            missing.append(path)
        elif action == "[UPDATE]":
            drifted.append(path)
        elif action == "[DELETE]":
            stale.append(path)
        elif action == "[UNCHANGED]":
            up_to_date.append(path)
        elif action == "[SKIP]":
            skipped.append(path)
    errors = list(result.errors)
    status_str = (
        "error" if errors else ("drifted" if (missing or drifted or stale) else "ok")
    )
    data = {
        "status": status_str,
        "missing": missing,
        "drifted": drifted,
        "stale": stale,
        "up_to_date": up_to_date,
        "warnings": result.warnings,
        "errors": errors,
    }
    if json_output:
        _emit_json(f"spec.{label.lower()}.status", status_str, data)
        raise typer.Exit(0 if status_str == "ok" else 1)

    from vaultspec_core.cli.rendering import Field, render_record
    from vaultspec_core.console import get_console

    status_style = (
        "red"
        if status_str == "error"
        else ("yellow" if status_str == "drifted" else "green")
    )
    fields = [
        Field("status", status_str, style=status_style),
        Field("missing", ", ".join(missing) or "none"),
        Field("drifted", ", ".join(drifted) or "none"),
        Field("stale", ", ".join(stale) or "none"),
        Field("up_to_date", f"{len(up_to_date)} files" if up_to_date else "none"),
    ]
    render_record(fields, title=f"{label} status")

    console = get_console()
    for w in result.warnings:
        console.print(f"  [yellow]-[/yellow] {w}")
    for e in errors:
        console.print(f"  [red]-[/red] {e}")
    if status_str != "ok":
        raise typer.Exit(1)


def _run_edit_command(
    name: str,
    base_dir: Path,
    label: str,
    is_dir: bool = False,
    editor: str | None = None,
) -> None:
    from vaultspec_core.core import resource_edit
    from vaultspec_core.core.exceptions import (
        EditorCancellationError,
        EditorResolutionError,
        EditorSubprocessError,
        VaultSpecError,
    )

    try:
        resource_edit(
            name=name,
            base_dir=base_dir,
            label=label,
            is_dir=is_dir,
            editor=editor,
        )
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
