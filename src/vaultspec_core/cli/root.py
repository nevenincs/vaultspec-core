"""Root Typer application: global callback, options, and top-level commands.

Mounts :mod:`.vault_cmd` and :mod:`.spec_cmd` sub-groups and defines
``install``, ``uninstall``, and ``sync`` commands that delegate to
:mod:`vaultspec_core.core.commands`. Exposes :func:`run` as the console-script
entry point. Depends on :mod:`vaultspec_core.config.workspace` for workspace
resolution and :mod:`vaultspec_core.core.types` for global path initialization.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

from vaultspec_core.cli._app import make_app
from vaultspec_core.cli._errors import handle_error as _handle_error
from vaultspec_core.cli._target import (
    TargetOption,
    apply_target,
    apply_target_install,
)
from vaultspec_core.core.enums import CliAction, InstallMode

if TYPE_CHECKING:
    from vaultspec_core.cli.rendering import OutcomeItem
    from vaultspec_core.core.types import SyncResult

logger = logging.getLogger(__name__)

# Main app definition must precede sub-app imports to enable them to
# reference it if needed (and to satisfy Typer's module-level discovery).
app = make_app(
    help=(
        "vaultspec-core: Workspace runtime for vaultspec-managed projects. "
        "All commands default to the current directory; use --target / -t to "
        "operate on a different directory. Run 'vaultspec-core install' to set "
        "up a project, then 'vaultspec-core vault add research --feature <tag>' "
        "to start the first feature. See 'vaultspec-core spec reference' for "
        "worked command examples."
    ),
    no_args_is_help=True,
    add_completion=False,
)

# ---- Global callback --------------------------------------------------------


def _version_callback(value: bool) -> None:
    if value:
        from vaultspec_core.cli_common import get_version

        typer.echo(get_version())
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    target: Annotated[
        Path | None,
        typer.Option(
            "--target",
            "-t",
            help="Target directory (defaults to current working directory)",
            dir_okay=True,
            file_okay=False,
            resolve_path=True,
        ),
    ] = None,
    debug: Annotated[
        bool, typer.Option("--debug", "-d", help="Enable debug logging")
    ] = False,
    _version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            help="Show version",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = False,
) -> None:
    """Initialize workspace and logging."""
    from vaultspec_core.cli._target import reset, set_root_target
    from vaultspec_core.logging_config import configure_logging

    log_level = logging.DEBUG if debug else logging.WARNING
    configure_logging(level=log_level, debug=debug)

    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit(0)

    # Store root-level target for subcommands; no workspace init here.
    # Each subcommand calls apply_target() / apply_target_install() which
    # merges root-level and subcommand-level --target with clear precedence.
    reset()
    set_root_target(target)
    ctx.obj = {}


# ---- Pre-flight helper -------------------------------------------------------


def _run_preflight(
    target: Path,
    action: str,
    provider: str = "all",
    *,
    force: bool = False,
    dry_run: bool = False,
    scope: str = "framework",
    render: bool = True,
) -> None:
    """Run diagnosis and resolution pre-flight.

    Executes preflight-safe resolution steps (manifest repair, gitignore
    repair, scaffold, adopt) and displays their outcomes. Non-preflight
    steps are shown as informational. Blocks on conflicts unless
    *dry_run* is ``True``.

    Raises :class:`typer.Exit` with code 1 if conflicts are present and
    *dry_run* is ``False``, or if any preflight execution step fails.
    """
    from vaultspec_core.core.diagnosis import diagnose
    from vaultspec_core.core.exceptions import VaultSpecError
    from vaultspec_core.core.executor import PREFLIGHT_ACTIONS, execute_plan
    from vaultspec_core.core.resolver import resolve

    try:
        diag = diagnose(target, scope=scope)
    except Exception:
        logger.warning("Pre-flight diagnosis failed", exc_info=True)
        return

    # resolve() raises a typed VaultSpecError for a refuse-and-tell condition
    # such as the below-floor version constraint. Route it through the same
    # clean error path the downstream mutating calls use rather than letting a
    # raw traceback escape preflight. render is the human-console flag, so its
    # inverse selects the machine-readable json error envelope.
    try:
        plan = resolve(diag, action, provider, force=force, dry_run=dry_run)
    except (VaultSpecError, OSError) as exc:
        _handle_error(exc, json_output=not render)
        return  # unreachable: _handle_error raises typer.Exit

    if not plan.warnings and not plan.conflicts and not plan.steps:
        return

    console = None
    if render:
        from vaultspec_core.console import get_console

        console = get_console()

    for warning in plan.warnings:
        if console:
            console.print(f"  [yellow]![/yellow] {warning}")

    # Execute preflight-safe resolution steps
    if plan.steps and not plan.blocked:
        exec_result = execute_plan(plan, target, dry_run=dry_run)

        for sr in exec_result.results:
            if not console:
                continue
            if sr.success:
                console.print(f"  [green]ok[/green] {sr.step.reason}")
            else:
                console.print(f"  [red]x[/red] {sr.step.reason}: {sr.error}")

        if exec_result.failed and not dry_run:
            raise typer.Exit(code=1)

    # Show non-preflight steps as informational (deferred to the main command)
    non_preflight = [s for s in plan.steps if s.action not in PREFLIGHT_ACTIONS]
    for step in non_preflight:
        if console:
            console.print(
                f"  [dim]>[/dim] {step.reason} "
                f"(detected, will be addressed by {action})"
            )

    if plan.conflicts:
        if console:
            console.print()
            for conflict in plan.conflicts:
                console.print(f"  [red]x[/red] {conflict}")
            console.print()
        if not dry_run:
            raise typer.Exit(code=1)


# ---- Top-level commands ------------------------------------------------------


@app.command("install")
def cmd_install(
    provider: Annotated[
        str,
        typer.Argument(
            help="Provider to install (all, core, claude, gemini, antigravity, codex)"
        ),
    ] = "all",
    target: TargetOption = None,
    upgrade: Annotated[
        bool,
        typer.Option("--upgrade", help="Re-seed bundled builtin content"),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview changes without writing"),
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force", help="Override contents if installation already exists"
        ),
    ] = False,
    skip: Annotated[
        list[str] | None,
        typer.Option(
            "--skip",
            help="Skip a component (core or provider name). Repeatable.",
        ),
    ] = None,
    mode: Annotated[
        InstallMode | None,
        typer.Option(
            "--mode",
            help=(
                "Provisioning mode: 'tool' (default, launched via uvx) or "
                "'dependency' (resolved through the project's own venv). "
                "Auto-detected from pyproject.toml when omitted."
            ),
        ),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    no_hints: Annotated[
        bool,
        typer.Option("--no-hints", help="Suppress next-step advisory hints"),
    ] = False,
) -> None:
    """Deploy the vaultspec framework to the target directory.

    Scaffolds the workspace structure and syncs all managed resources.
    Use --upgrade to update builtin rules without re-scaffolding.
    Use --skip to exclude components on retry (e.g. --skip core --skip claude).
    """
    from vaultspec_core.core.commands import install_run
    from vaultspec_core.core.exceptions import VaultSpecError

    skip = list(skip or [])
    path: Path = apply_target_install(target)

    # Guard: refuse to create deeply nested paths  - only allow creating the
    # final directory component.  This prevents accidental scaffolding of
    # arbitrary directory trees from typos or path traversal.
    if not path.exists():
        if not path.parent.exists():
            typer.echo(
                f"Error: Parent directory does not exist: {path.parent}\n"
                f"Create intermediate directories manually or use an existing path.",
                err=True,
            )
            raise typer.Exit(code=1)
        if not dry_run:
            path.mkdir(parents=False, exist_ok=True)

    fw_path = path / ".vaultspec"
    if fw_path.exists() and not fw_path.is_dir():
        typer.echo(
            f"Error: {fw_path} exists but is a file, not a directory.\n"
            "  Remove the file and re-run install.",
            err=True,
        )
        raise typer.Exit(code=1)

    # Preflight rewrites a stale managed gitignore block, so capture
    # whether this workspace is still on the pre-reversal policy first -
    # an upgrade that carries it across prints the sharing-policy notice.
    from vaultspec_core.core.gitignore import block_is_pre_reversal

    gitignore_was_pre_reversal = upgrade and not dry_run and block_is_pre_reversal(path)

    _run_preflight(
        path,
        action=CliAction.UPGRADE if upgrade else CliAction.INSTALL,
        provider=provider,
        force=force,
        dry_run=dry_run,
        scope="framework",
        render=not json_output,
    )

    try:
        result = install_run(
            path=path,
            provider=provider,
            upgrade=upgrade,
            dry_run=dry_run,
            force=force,
            skip=set(skip),
            mode=mode,
        )
    except (VaultSpecError, OSError) as exc:
        _handle_error(exc, json_output=json_output)
        return  # unreachable, but satisfies type checker

    # The upgrade path re-seeds bundled builtins. Per the
    # cli-sync-vocabulary ADR it reports per-builtin canonical outcomes
    # (created/updated/unchanged) through the shared renderer instead of
    # the old "Re-seeded N / Upgrade complete" wording.
    if result["action"] == "upgrade":
        from vaultspec_core.cli.rendering import (
            Outcome,
            OutcomeItem,
            emit_next_step_hint,
            emit_outcomes,
            render_sharing_policy,
        )
        from vaultspec_core.cli_common import get_version

        action_map = {
            "[ADD]": Outcome.CREATED,
            "[UPDATE]": Outcome.UPDATED,
            "[UNCHANGED]": Outcome.UNCHANGED,
        }
        outcomes = [
            OutcomeItem(name=rel, outcome=action_map.get(action, Outcome.UPDATED))
            for rel, action in result["items"]
        ]
        # Stamp the framework version into the heading and the JSON so an
        # operator can see *which* version they are now on, not just that
        # something changed.
        version = get_version()
        verb = "Upgrade preview" if result.get("dry_run") else "Upgrade"
        title = f"{verb} {version} -> {path}"

        hint_dict = emit_next_step_hint(
            command="install",
            outcome="updated",
            json_output=json_output,
            no_hints=no_hints,
        )

        code = emit_outcomes(
            outcomes,
            command="install",
            title=title,
            json_output=json_output,
            extra_json={"version": version},
            hints=hint_dict,
        )
        # Surface the new sharing policy when this upgrade carried the
        # workspace off the pre-reversal team-hidden gitignore policy.
        if not json_output and gitignore_was_pre_reversal:
            render_sharing_policy()
        raise typer.Exit(code)

    hint_dict = None
    if json_output and result["action"] != "dry_run":
        from vaultspec_core.cli.rendering import emit_next_step_hint

        hint_dict = emit_next_step_hint(
            command="install",
            outcome="created",
            json_output=True,
            no_hints=no_hints,
        )

    if json_output:
        import json

        from vaultspec_core.cli.rendering import json_envelope

        result["path"] = str(result["path"])
        status = "unchanged" if result["action"] == "dry_run" else "created"
        envelope = json_envelope("install", status, result, hints=hint_dict)
        typer.echo(json.dumps(envelope, indent=2, default=str))
        raise typer.Exit(0)

    if result["action"] == "dry_run":
        from vaultspec_core.cli.rendering import render_dry_run_tree
        from vaultspec_core.core.dry_run import (
            DryRunItem,
            DryRunStatus,
        )

        items = result["items"]
        dry_items = [
            DryRunItem(
                path=str(path / rel).replace("\\", "/"),
                status=(
                    DryRunStatus.EXISTS if (path / rel).exists() else DryRunStatus.NEW
                ),
                label=label,
            )
            for rel, label in items
        ]
        render_dry_run_tree(dry_items, title=f"Install preview -> {path}")
    else:
        from vaultspec_core.cli.rendering import (
            emit_next_step_hint,
            render_install_summary,
            render_sharing_policy,
        )

        render_install_summary(
            result.get("source_counts", {}),
            path=str(path),
            providers=result.get("providers", []),
            has_mcp=result.get("has_mcp", False),
        )
        render_sharing_policy()
        emit_next_step_hint(
            command="install",
            outcome="created",
            json_output=False,
            no_hints=no_hints,
        )


@app.command("uninstall")
def cmd_uninstall(
    provider: Annotated[
        str,
        typer.Argument(
            help="Provider to uninstall (all, core, claude, gemini, antigravity, codex)"
        ),
    ] = "all",
    target: TargetOption = None,
    remove_vault: Annotated[
        bool,
        typer.Option(
            "--remove-vault",
            help="Also remove .vault/ documentation (preserved by default)",
        ),
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Preview changes without removing")
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", help="Required to execute. Uninstall is destructive."),
    ] = False,
    skip: Annotated[
        list[str] | None,
        typer.Option(
            "--skip",
            help="Skip a component (core or provider name). Repeatable.",
        ),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Remove the vaultspec framework from the target directory.

    Removes all managed artifacts (.vaultspec/, provider dirs, generated configs).
    The .vault/ documentation corpus is preserved by default.
    Use a provider name to remove only that provider's artifacts.
    Use --skip to exclude components (e.g. --skip claude --skip codex).
    """
    from vaultspec_core.core.commands import uninstall_run
    from vaultspec_core.core.exceptions import VaultSpecError

    skip = list(skip or [])
    path: Path = apply_target_install(target)

    if not path.exists():
        typer.echo(f"Error: Target directory does not exist: {path}", err=True)
        raise typer.Exit(code=1)

    _run_preflight(
        path,
        action=CliAction.UNINSTALL,
        provider=provider,
        force=force,
        dry_run=dry_run,
        scope="framework",
        render=not json_output,
    )

    try:
        result = uninstall_run(
            path=path,
            provider=provider,
            keep_vault=not remove_vault,
            dry_run=dry_run,
            force=force,
            skip=set(skip),
        )
    except (VaultSpecError, OSError) as exc:
        _handle_error(exc, json_output=json_output)
        return

    if json_output:
        import json

        from vaultspec_core.cli.rendering import json_envelope

        result["path"] = str(result["path"])
        if result["action"] == "dry_run":
            status = "unchanged"
        elif result.get("removed"):
            status = "removed"
        else:
            status = "unchanged"
        envelope = json_envelope("uninstall", status, result)
        typer.echo(json.dumps(envelope, indent=2, default=str))
        raise typer.Exit(0)

    # Render result
    from vaultspec_core.console import get_console

    console = get_console()
    removed = result.get("removed", [])

    if result["action"] == "dry_run":
        from vaultspec_core.cli.rendering import render_dry_run_tree
        from vaultspec_core.core.dry_run import (
            DryRunItem,
            DryRunStatus,
        )

        dry_items = [
            DryRunItem(path=item_path, status=DryRunStatus.DELETE, label=label)
            for item_path, label in removed
        ]
        render_dry_run_tree(dry_items, title=f"Uninstall preview -> {path}")
    elif removed:
        from vaultspec_core.cli.rendering import render_uninstall_summary

        render_uninstall_summary(
            removed, path=str(path), keep_vault=result.get("keep_vault", True)
        )
    else:
        console.print("Nothing to remove  - vaultspec is not installed at this path.")


@app.command("sync")
def cmd_sync(
    provider: Annotated[
        str,
        typer.Argument(
            help="Provider to sync (all, claude, gemini, antigravity, codex)"
        ),
    ] = "all",
    target: TargetOption = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview changes")] = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Complete sync: prune stale files and overwrite user-authored content",
        ),
    ] = False,
    skip: Annotated[
        list[str] | None,
        typer.Option(
            "--skip",
            help="Skip a component (core or provider name). Repeatable.",
        ),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Sync rules, skills, agents, configs, system prompts, and MCPs.

    This is the authoritative complete sync from .vaultspec/ to enrolled
    provider outputs. By default sync is non-destructive: missing files are
    added and changed files are updated, but stale destination files and
    user-authored system/config files are left untouched (with warnings).

    Use --force for a complete sync that prunes stale files and overwrites
    user-authored content to match the .vaultspec/ source exactly.

    Defaults to syncing all providers. Pass a provider name to sync only
    that provider (e.g. 'vaultspec-core sync claude').
    Use --skip to exclude providers (e.g. --skip claude --skip codex).
    """
    skip = list(skip or [])
    apply_target(target, split_source=True, json_output=json_output)
    if provider == "core":
        typer.echo(
            "Error: 'core' is not a valid sync target. "
            "The sync source is .vaultspec/ (core) itself.\n"
            "  Hint: use 'vaultspec-core sync all' to sync all providers, "
            "or 'vaultspec-core install --upgrade' to update the framework.",
            err=True,
        )
        raise typer.Exit(code=1)

    from vaultspec_core.core.types import get_context

    try:
        ctx = get_context()
        sync_target = ctx.target_dir
    except LookupError:
        sync_target = target or Path.cwd()

    _run_preflight(
        sync_target,
        action=CliAction.SYNC,
        provider=provider,
        force=force,
        dry_run=dry_run,
        scope="sync",
        render=not json_output,
    )

    from vaultspec_core.core.commands import sync_provider
    from vaultspec_core.core.exceptions import VaultSpecError

    try:
        results = sync_provider(provider, dry_run=dry_run, force=force, skip=set(skip))
    except (VaultSpecError, OSError) as exc:
        _handle_error(exc, json_output=json_output)
        return

    from vaultspec_core.console import get_console

    console = get_console()

    if dry_run:
        if json_output:
            import json

            from vaultspec_core.cli.rendering import (
                json_envelope,
                outcomes_as_json,
            )

            outcomes = _collect_sync_outcomes(results, provider, skip)
            inner = outcomes_as_json(outcomes)
            envelope = json_envelope(
                "sync", str(inner["status"]), {"items": inner["items"]}
            )
            typer.echo(json.dumps(envelope, indent=2))
            raise typer.Exit(0)

        from vaultspec_core.cli.rendering import render_dry_run_tree
        from vaultspec_core.core.dry_run import (
            DryRunItem,
            DryRunStatus,
        )
        from vaultspec_core.core.types import get_context

        action_map = {
            "[ADD]": DryRunStatus.NEW,
            "[UPDATE]": DryRunStatus.UPDATE,
            "[UNCHANGED]": DryRunStatus.EXISTS,
            "[SKIP]": DryRunStatus.EXISTS,
            "[DELETE]": DryRunStatus.DELETE,
        }
        all_items = []
        for r in results:
            for item_path, action in r.items:
                status = action_map.get(action, DryRunStatus.UPDATE)
                all_items.append(
                    DryRunItem(
                        path=item_path,
                        status=status,
                        label=_infer_label(item_path),
                    )
                )
        if all_items:
            _target_dir = get_context().target_dir
            title = f"Sync preview -> {_target_dir}"
            if provider != "all":
                title = f"Sync preview ({provider}) -> {_target_dir}"
            render_dry_run_tree(all_items, title=title)
        else:
            console.print("[dim]Sync preview: no changes[/dim]")
        raise typer.Exit(0)

    # Non-dry-run: route every provider through the canonical outcome
    # renderer. Per the cli-sync-vocabulary ADR (audit findings
    # S2/S8/S10/S19), one helper feeds text and JSON from a single
    # OutcomeItem list, and each provider becomes a group so the output
    # stays per-provider readable without a bespoke summary loop.
    from vaultspec_core.cli.rendering import emit_outcomes
    from vaultspec_core.core.manifest import installed_tool_configs

    active_configs = installed_tool_configs()
    if provider == "all":
        active_names = [
            cfg.name
            for tool, cfg in active_configs.items()
            if tool.value not in skip and cfg.name not in skip
        ]
    else:
        active_names = [
            cfg.name
            for tool, cfg in active_configs.items()
            if (tool.value == provider or cfg.name == provider)
            and tool.value not in skip
            and cfg.name not in skip
        ]

    if not active_names and not json_output:
        console.print("[dim]No enabled providers to sync.[/dim]")
        raise typer.Exit(0)

    outcomes = _collect_sync_outcomes(results, provider, skip)

    all_warnings = [w for r in results for w in r.warnings]
    extra_json = {"warnings": all_warnings} if all_warnings else None
    code = emit_outcomes(
        outcomes,
        command="sync",
        title="Sync",
        json_output=json_output,
        extra_json=extra_json,
    )

    if not json_output:
        from vaultspec_core.builtins import check_outdated

        vaultspec_dir = sync_target / ".vaultspec"
        outdated = check_outdated(vaultspec_dir) if vaultspec_dir.is_dir() else []
        if outdated:
            console.print()
            console.print(
                f"[bold yellow]Upgrade available:[/bold yellow] "
                f"{len(outdated)} builtin(s) in the installed "
                f"vaultspec-core package are newer than .vaultspec/:"
            )
            for path in outdated:
                console.print(f"  [yellow]-[/yellow] {path}")
            from vaultspec_core.cli.rendering import (
                hints_suppressed,
                render_next_actions,
            )

            if not hints_suppressed():
                render_next_actions(
                    [
                        (
                            "Update builtins to the packaged version",
                            "vaultspec-core install --upgrade",
                        ),
                        ("Re-sync after upgrading", "vaultspec-core sync"),
                    ]
                )

        if all_warnings:
            console.print()
            console.print(
                f"[bold yellow]Warning:[/bold yellow] "
                f"{len(all_warnings)} item(s) differ from .vaultspec/ source. "
                f"Use [bold]--force[/bold] to resolve:"
            )
            for warning in all_warnings:
                console.print(f"  [yellow]-[/yellow] {warning}")

        # Warn only when a clean run genuinely found nothing to project:
        # no changes, no skips, and no files already in place.
        total_changes = sum(r.added + r.updated for r in results)
        total_skipped = sum(r.skipped for r in results)
        total_unchanged = sum(r.unchanged for r in results)
        if (
            code == 0
            and active_names
            and total_changes == 0
            and total_skipped == 0
            and total_unchanged == 0
            and not all_warnings
        ):
            console.print(
                "\n[bold yellow]Warning:[/bold yellow] Sync produced 0 files. "
                "The .vaultspec/ source directories may be empty."
            )
            from vaultspec_core.cli.rendering import (
                hints_suppressed,
                render_next_actions,
            )

            if not hints_suppressed():
                render_next_actions(
                    [("Re-seed builtin content", "vaultspec-core install --upgrade")]
                )

    raise typer.Exit(code)


def _collect_sync_outcomes(
    results: list[SyncResult], provider: str, skip: list[str]
) -> list[OutcomeItem]:
    """Flatten sync-pass results into per-provider-grouped outcomes.

    Each resource pass carries per-provider results in ``per_tool``;
    global passes (e.g. mcps) carry only the aggregate and are grouped
    under their resource label. Shared by the text and ``--json``
    renderings of both ``sync`` and ``sync --dry-run`` so the surfaces
    cannot drift apart.
    """
    from vaultspec_core.cli.rendering import sync_outcomes

    labels = ["rules", "skills", "agents", "system", "config"]
    if provider == "all" and "mcp" not in skip:
        labels.append("mcps")
    outcomes: list[OutcomeItem] = []
    # Results beyond the known positional resource passes (e.g. the trailing
    # structural-backfill pass, issue #133) are grouped per inferred provider so
    # the surface never crashes on a length mismatch and still reports them.
    for index, r in enumerate(results):
        label = labels[index] if index < len(labels) else None
        if r.per_tool:
            for tool_name, tool_result in r.per_tool.items():
                outcomes.extend(sync_outcomes(tool_result, group=tool_name))
        elif label is not None:
            outcomes.extend(sync_outcomes(r, group=label))
        else:
            for item_path, _action in r.items:
                outcomes.extend(
                    sync_outcomes(
                        _single_item_result(r, item_path),
                        group=_infer_label(item_path),
                    )
                )
    return outcomes


def _single_item_result(source: SyncResult, item_path: str) -> SyncResult:
    """Return a one-item SyncResult mirroring ``item_path``'s action.

    Used to re-group structural-backfill items under their inferred provider
    label without mutating the original aggregate result.
    """
    from vaultspec_core.core.types import SyncResult as _SyncResult

    single = _SyncResult()
    for path, action in source.items:
        if path != item_path:
            continue
        single.items.append((path, action))
        if action == "[ADD]":
            single.added += 1
        elif action == "[UPDATE]":
            single.updated += 1
        elif action == "[DELETE]":
            single.pruned += 1
    return single


def _infer_label(item_path: str) -> str:
    """Infer a human-readable label from a sync output path."""
    p = item_path.replace("\\", "/")

    provider_map = {
        "/.claude/": "claude",
        "/.gemini/": "gemini",
        "/.agents/": "antigravity",
        "/.codex/": "codex",
    }
    provider_name = ""
    for segment, name in provider_map.items():
        if segment in p:
            provider_name = name
            break

    config_map = {
        "/CLAUDE.md": "claude (config)",
        "/GEMINI.md": "gemini (config)",
        "/AGENTS.md": "codex (config)",
        "/config.toml": "codex (config)",
    }
    for suffix, lbl in config_map.items():
        if p.endswith(suffix):
            return lbl

    if "/rules/" in p:
        return f"{provider_name} (rules)" if provider_name else "rules"
    if "/skills/" in p:
        return f"{provider_name} (skills)" if provider_name else "skills"
    if "/agents/" in p:
        return f"{provider_name} (agents)" if provider_name else "agents"
    if "SYSTEM.md" in p or "system" in p.lower():
        return f"{provider_name} (system)" if provider_name else "system"

    return provider_name or ""


@app.command("check-providers", hidden=True)
def cmd_check_providers() -> None:
    """Guard against committing provider artifacts.

    Inspects the git staging area for files that should never be
    committed (provider directories, generated configs, manifests).
    Used as a pre-commit hook entry point.
    """
    from vaultspec_core.core.commands import check_staged_provider_artifacts

    violations = check_staged_provider_artifacts()
    if violations:
        typer.echo(
            "Error: provider artifacts must not be committed:",
            err=True,
        )
        for v in violations:
            typer.echo(f"  {v}", err=True)
        typer.echo(
            "\nRun 'git reset HEAD <file>' to unstage, "
            "or 'git rm --cached <file>' to untrack.",
            err=True,
        )
        raise typer.Exit(code=1)


@app.command("doctor")
def cmd_doctor(
    target: TargetOption = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Diagnose overall workspace and vault health.

    Runs both spec workspace diagnosis and vault check-all under a unified exit code.

    Exit codes: 0 = all ok, 1 = warnings, 2 = errors.
    """
    import contextlib
    import dataclasses
    import json
    import logging
    from pathlib import Path

    import typer

    from vaultspec_core.cli.rendering import json_envelope
    from vaultspec_core.cli.spec_cmd import _doctor_exit_code, _render_diagnosis_table
    from vaultspec_core.console import get_console
    from vaultspec_core.core.diagnosis import diagnose
    from vaultspec_core.vaultcore.checks import render_check_result, run_all_checks

    effective_dir = target or Path.cwd()
    effective_dir = effective_dir.resolve()

    if not effective_dir.exists():
        typer.echo(f"Error: target directory does not exist: {effective_dir}", err=True)
        raise typer.Exit(code=2)

    previous_logging_disable = logging.root.manager.disable
    if json_output:
        logging.disable(logging.CRITICAL)

    try:
        with contextlib.suppress(Exception):
            apply_target(target)

        try:
            diag = diagnose(effective_dir, scope="full")
        except Exception as exc:
            typer.echo(f"Error: workspace diagnosis failed: {exc}", err=True)
            raise typer.Exit(code=2) from None

        try:
            results = run_all_checks(effective_dir)
        except Exception as exc:
            typer.echo(f"Error: vault checking failed: {exc}", err=True)
            raise typer.Exit(code=2) from None

    finally:
        if json_output:
            logging.disable(previous_logging_disable)

    spec_exit_code = _doctor_exit_code(diag)
    vault_has_errors = any(r.error_count for r in results)
    vault_has_warnings = any(r.warning_count for r in results)

    if spec_exit_code == 2 or vault_has_errors:
        exit_code = 2
    elif spec_exit_code == 1 or vault_has_warnings:
        exit_code = 1
    else:
        exit_code = 0

    if json_output:
        data = {
            "spec": dataclasses.asdict(diag),
            "vault": {"checks": [dataclasses.asdict(r) for r in results]},
        }
        envelope = json_envelope(
            "doctor",
            "failed" if exit_code == 2 else "unchanged",
            data,
        )
        typer.echo(json.dumps(envelope, indent=2, default=str))
        raise typer.Exit(code=exit_code)

    console = get_console()
    _render_diagnosis_table(console, diag)
    console.print()
    console.print("[bold]Vault Check - All[/bold]")
    for r in results:
        render_check_result(console, r, verbose=False)

    raise typer.Exit(code=exit_code)


def _register_subcommands() -> None:
    """Mount sub-apps with deferred imports to avoid circular dependencies."""
    from .config_cmd import config_app
    from .migrations_cmd import migrations_app
    from .spec_cmd import spec_app
    from .status_cmd import register as register_status
    from .vault_cmd import vault_app

    # The zeroth-move orientation verb is top-level, not nested
    # under `vault`; it is the most reachable command for an unknown project.
    register_status(app)

    app.add_typer(vault_app, name="vault")
    app.add_typer(spec_app, name="spec")
    app.add_typer(migrations_app, name="migrations")
    app.add_typer(config_app, name="config")


_register_subcommands()


# ---- Entry point -------------------------------------------------------------


def run() -> None:
    """CLI entry point for console scripts."""
    app()


if __name__ == "__main__":
    run()
