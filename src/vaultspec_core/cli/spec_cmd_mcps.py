"""``vaultspec-core spec mcps`` - manage canonical MCP definitions.

Defines :data:`mcps_app`, mounted by :mod:`vaultspec_core.cli.spec_cmd`
onto :data:`~vaultspec_core.cli.spec_cmd_app.spec_app` as the ``mcps``
command group. Delegates to :mod:`vaultspec_core.core` CRUD functions via
lazy imports to avoid circular-import issues.
"""

import json
from typing import TYPE_CHECKING, Annotated

import typer

if TYPE_CHECKING:
    from pathlib import Path

from vaultspec_core.cli._app import make_app
from vaultspec_core.cli._errors import handle_error as _handle_error
from vaultspec_core.cli._target import TargetOption, apply_target
from vaultspec_core.cli.spec_cmd_shared import (
    apply_provider_filter,
    emit_json,
    emit_sync_result,
    print_complete_sync_notice,
    print_source_mutation_notice,
)

mcps_app = make_app(
    help="Manage canonical MCP definitions and provider-native enrollment.",
    no_args_is_help=True,
)


@mcps_app.command("list")
def cmd_mcps_list(
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """List canonical MCP server definitions."""
    apply_target(target)
    from vaultspec_core.core import mcp_list

    items = mcp_list()

    if json_output:
        emit_json("spec.mcps.list", "unchanged", {"items": items})
        raise typer.Exit(0)

    from vaultspec_core.cli.rendering import Column, render_listing, summary_line

    rows = [{"name": item["name"], "source": item["source"]} for item in items]
    render_listing(
        rows,
        [Column("name"), Column("source")],
        title="mcps",
        summary=summary_line(len(rows), "mcps"),
        empty="no mcps",
    )


@mcps_app.command("status")
def cmd_mcps_status(
    provider: Annotated[
        str,
        typer.Argument(help="Provider target (all, claude, antigravity, codex)"),
    ] = "all",
    scope: Annotated[
        str,
        typer.Option(
            "--scope",
            help="Enrollment scope (project, local, user); default: project",
        ),
    ] = "project",
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Inspect provider-native MCP enrollment status."""
    apply_target(target)
    apply_provider_filter(provider)
    from vaultspec_core.core import mcp_status

    status = mcp_status(provider=provider, scope=scope)

    if json_output:
        emit_json("spec.mcps.status", "unchanged", status)
        raise typer.Exit(0 if status["status"] == "ok" else 1)

    from vaultspec_core.cli.rendering import Column, render_listing
    from vaultspec_core.console import get_console

    rows = [
        {
            "provider": name,
            "scope": data["scope"],
            "status": data["status"],
            "config": data["config_path"],
            "managed": ", ".join(data["managed"]) or "none",
            "missing": ", ".join(data["missing"]) or "none",
            "drifted": ", ".join(data["drifted"]) or "none",
            "external": ", ".join(data["external"]) or "none",
        }
        for name, data in status["providers"].items()
    ]
    render_listing(
        rows,
        [
            Column("provider"),
            Column("scope"),
            Column("status"),
            Column("config"),
            Column("managed"),
            Column("missing"),
            Column("drifted"),
            Column("external"),
        ],
        title="mcps status",
        summary=f"{status['status']}: {len(rows)} provider target(s)",
        empty="no enrolled MCP-capable providers",
    )

    console = get_console()
    for warning in status["warnings"]:
        console.print(f"  [yellow]-[/yellow] {warning}")
    if status["status"] != "ok":
        raise typer.Exit(code=1)


@mcps_app.command("add")
def cmd_mcps_add(
    name: Annotated[str, typer.Option("--name", help="MCP server name")],
    config: Annotated[
        str | None, typer.Option("--config", help="Server config as JSON string")
    ] = None,
    force: Annotated[bool, typer.Option("--force", help="Overwrite existing")] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Add or replace a canonical MCP server definition."""
    apply_target(target)
    import json as json_mod

    from vaultspec_core.core import mcp_add
    from vaultspec_core.core.exceptions import VaultSpecError

    parsed_config = None
    if config is not None:
        try:
            parsed_config = json_mod.loads(config)
        except json_mod.JSONDecodeError as exc:
            typer.echo(f"Error: Invalid JSON config: {exc}", err=True)
            raise typer.Exit(code=1) from exc

    try:
        file_path = mcp_add(name=name, config=parsed_config, force=force)
    except VaultSpecError as exc:
        _handle_error(exc, json_output=json_output)
        return

    if json_output:
        emit_json("spec.mcps.add", "created", {"path": str(file_path)})
        raise typer.Exit(0)

    print_source_mutation_notice(file_path, action="MCP source updated")


@mcps_app.command("remove")
def cmd_mcps_remove(
    name: Annotated[str, typer.Argument(help="MCP server name")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Remove a canonical MCP server definition."""
    apply_target(target)
    from vaultspec_core.core import mcp_remove
    from vaultspec_core.core.exceptions import VaultSpecError

    if not force and not typer.confirm(f"Remove MCP definition '{name}'?"):
        raise typer.Abort()

    try:
        removed_path = mcp_remove(name=name)
    except VaultSpecError as exc:
        _handle_error(exc, json_output=json_output)
        return

    if json_output:
        emit_json("spec.mcps.remove", "removed", {"removed": name})
        raise typer.Exit(0)

    print_source_mutation_notice(removed_path, action="MCP source removed")


@mcps_app.command("sync")
def cmd_mcps_sync(
    provider: Annotated[
        str,
        typer.Argument(help="Provider target (all, claude, antigravity, codex)"),
    ] = "all",
    scope: Annotated[
        str,
        typer.Option(
            "--scope",
            help="Enrollment scope (project, local, user); default: project",
        ),
    ] = "project",
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Preview without writing files")
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", help="Adopt or overwrite same-name enrollment"),
    ] = False,
    prune: Annotated[
        bool,
        typer.Option("--prune", help="Remove owned enrollment with deleted sources"),
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Reconcile canonical definitions into provider-native enrollment."""
    apply_target(target)
    apply_provider_filter(provider)
    from vaultspec_core.core import mcp_sync

    result = mcp_sync(
        provider=provider,
        scope=scope,
        force=force,
        prune=prune,
        dry_run=dry_run,
    )

    if not json_output:
        print_complete_sync_notice(resource="MCP", mcp=True)
    emit_sync_result(result, label="MCPs", dry_run=dry_run, json_output=json_output)


@mcps_app.command("trust")
def cmd_mcps_trust(
    provider: Annotated[str, typer.Argument(help="Provider target to approve")] = "all",
    scope: Annotated[str, typer.Option("--scope", help="Enrollment scope")] = "project",
    revoke: Annotated[
        bool, typer.Option("--revoke", help="Withdraw workspace grants")
    ] = False,
    source_from_cwd: Annotated[
        bool,
        typer.Option(
            "--source-from-cwd",
            help="Approve CWD sources for a top-level sync --target destination",
        ),
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Approve exact MCP commands for enrollment after reviewing them at a terminal.

    Approval is host-local and binds definition bytes, rendered command, args,
    environment, provider, scope, and target. Changes require another approval.
    Revocation prevents further enrollment; use uninstall to remove deployed entries.
    """
    apply_target(target, split_source=source_from_cwd, json_output=json_output)
    from vaultspec_core.config import is_unattended
    from vaultspec_core.core.exceptions import VaultSpecError
    from vaultspec_core.core.mcps_definitions import collect_mcp_servers
    from vaultspec_core.core.mcps_native import normalized_sources
    from vaultspec_core.core.mcps_targets import resolve_mcp_targets
    from vaultspec_core.core.mcps_trust import McpApproval, grant
    from vaultspec_core.core.mcps_trust import revoke as revoke_trust
    from vaultspec_core.core.types import SyncResult, get_context
    from vaultspec_core.core.workspace_mode import (
        CORE_DISTRIBUTION_NAME,
        resolve_render_mode,
    )

    root = get_context().target_dir
    if revoke:
        removed = revoke_trust(root)
        if json_output:
            emit_json("spec.mcps.trust", "removed", {"revoked": removed})
        else:
            typer.echo(f"Withdrew {removed} MCP enrollment grant(s).")
        return
    if is_unattended(json_output=json_output):
        _handle_error(
            VaultSpecError(
                "MCP approval requires review and confirmation at an "
                "interactive terminal."
            ),
            json_output=json_output,
        )
        return
    try:
        targets = resolve_mcp_targets(provider, scope=scope, target_dir=root)
        mode = resolve_render_mode(root, package=CORE_DISTRIBUTION_NAME)
        digests: dict[Path, str] = {}
        warnings: list[str] = []
        sources = collect_mcp_servers(
            warnings=warnings, mode=mode, target=root, digests=digests
        )
        approvals: list[McpApproval] = []
        for native_target in targets:
            result = SyncResult()
            normalized = normalized_sources(sources, native_target, result)
            warnings.extend(result.warnings)
            for name, (path, config) in normalized.items():
                approval = McpApproval.capture(
                    root, native_target, name, path, config, digests[path]
                )
                approvals.append(approval)
                # JSON escaping makes control characters visible without changing
                # the snapshot that will be granted after confirmation.
                typer.echo(
                    json.dumps(
                        {
                            "name": name,
                            "source": approval.source,
                            "provider": approval.provider,
                            "scope": approval.scope,
                            "target": approval.target,
                            "definition_digest": approval.definition_digest,
                            "launch": json.loads(approval.launch),
                        },
                        indent=2,
                    )
                )
        for warning in warnings:
            # Repository filenames also appear in warnings. Escape terminal
            # controls so an invalid sibling cannot erase the approval display.
            typer.echo(json.dumps(warning, ensure_ascii=True), err=True)
        if not approvals:
            typer.echo("No valid MCP definitions to approve.")
            return
        typer.echo(
            "These repository commands may later be launched by your provider as you, "
            "with your credentials and environment. Approval is stored outside this "
            "workspace and applies only to the exact definitions and launches "
            "shown above."
        )
        try:
            confirmed = typer.confirm("Approve these MCP enrollments?", default=False)
        except (typer.Abort, EOFError, KeyboardInterrupt):
            confirmed = False
        if not confirmed:
            typer.echo("MCP definitions were not approved.", err=True)
            raise typer.Exit(code=1)
        grant(approvals)
        typer.echo(
            f"Approved {len(approvals)} MCP enrollment(s); run spec mcps sync next."
        )
    except (VaultSpecError, OSError) as exc:
        _handle_error(VaultSpecError(str(exc)), json_output=json_output)


@mcps_app.command("uninstall")
def cmd_mcps_uninstall(
    provider: Annotated[
        str,
        typer.Argument(help="Provider target (all, claude, antigravity, codex)"),
    ] = "all",
    scope: Annotated[
        str,
        typer.Option(
            "--scope",
            help="Enrollment scope (project, local, user); default: project",
        ),
    ] = "project",
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Preview removals")
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", help="Required to remove owned host entries"),
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Remove Vaultspec-owned provider-native MCP enrollment."""
    apply_target(target)
    apply_provider_filter(provider)
    if not force and not dry_run:
        typer.echo(
            "Error: MCP uninstall is destructive. Pass --force or use --dry-run.",
            err=True,
        )
        raise typer.Exit(code=1)

    from vaultspec_core.core import get_context, mcp_uninstall

    result = mcp_uninstall(
        get_context().target_dir,
        provider=provider,
        scope=scope,
        dry_run=dry_run,
    )
    emit_sync_result(
        result,
        label="MCPs uninstall",
        dry_run=dry_run,
        json_output=json_output,
        command="spec.mcps.uninstall",
    )
