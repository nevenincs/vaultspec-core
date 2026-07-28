"""``vaultspec-core install`` and ``vaultspec-core uninstall``.

Defines :func:`cmd_install` and :func:`cmd_uninstall`, mounted by
:mod:`vaultspec_core.cli.root` as the ``install`` and ``uninstall`` commands
on :data:`~vaultspec_core.cli.root_app.app`.
"""

from __future__ import annotations

import logging
from pathlib import Path  # noqa: TC003 - Typer evaluates the --target annotation.
from typing import Annotated

import typer

from vaultspec_core.cli._errors import handle_error as _handle_error
from vaultspec_core.cli._target import TargetOption, apply_target_install
from vaultspec_core.cli.root_preflight import _run_preflight
from vaultspec_core.core.enums import CliAction, InstallMode

logger = logging.getLogger(__name__)


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
            help=(
                "Skip a component: core, a provider name, mcp, or "
                "precommit. Repeatable."
            ),
        ),
    ] = None,
    mode: Annotated[
        InstallMode | None,
        typer.Option(
            "--mode",
            help=(
                "Provisioning mode: 'tool' (default, launched via uvx), "
                "'dependency' (a runtime project dependency resolved through the "
                "project's own venv, ships in built distributions), or 'dev' "
                "(the default dev dependency group; renders like dependency but "
                "does not ship in built distributions). Auto-detected from "
                "pyproject.toml when omitted."
            ),
        ),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    no_hints: Annotated[
        bool,
        typer.Option("--no-hints", help="Suppress next-step advisory hints"),
    ] = False,
) -> None:
    """Install Vaultspec resources for the selected providers.

    Scaffolds the workspace structure and syncs all managed resources.
    Use --upgrade to update builtin rules without re-scaffolding.
    Use --skip to exclude components on retry (e.g. --skip core --skip claude);
    valid targets are core, provider names, mcp, and precommit.
    For MCP-capable providers, installation reconciles canonical MCP definitions
    into project-scope provider-native configuration. It does not start MCP
    servers or grant provider trust.
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

    # Pre-flight establishes the runtime manifest when this workspace is
    # adoptable, which flips the framework signal to PRESENT. Capture the
    # pre-adoption observation first so install_run can tell "just adopted" from
    # "already installed" and stay on the additive path instead of demanding
    # --force against content the clone legitimately tracks.
    from vaultspec_core.core.diagnosis.collectors import collect_framework_presence
    from vaultspec_core.core.diagnosis.signals import FrameworkSignal

    adopting = collect_framework_presence(path) is FrameworkSignal.ADOPTABLE

    _run_preflight(
        path,
        action=CliAction.UPGRADE if upgrade else CliAction.INSTALL,
        provider=provider,
        force=force,
        dry_run=dry_run,
        scope="framework",
        render=not json_output,
        skip=set(skip),
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
            adopt=adopting,
        )
    except (VaultSpecError, OSError) as exc:
        _handle_error(exc, json_output=json_output)
        return  # unreachable, but satisfies type checker

    # Surface the moment-of-choice dependency-leak advisory (install-parity ADR
    # D3): install_run emits it only when this run newly elects dependency mode,
    # so a persisted-declaration workspace stays silent. On the JSON path it
    # rides in the result envelope below rather than the human console.
    if not json_output:
        from vaultspec_core.console import get_console

        _console = get_console()
        for warning in result.get("warnings", []):
            _console.print(f"  [yellow]![/yellow] {warning}")

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
            extra_json={"version": version, "warnings": result.get("warnings", [])},
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
        skip=set(skip),
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
