"""``vaultspec-core spec hooks`` - agent-runtime hooks, authored once per workspace.

Defines :data:`hooks_app`, mounted by :mod:`vaultspec_core.cli.spec_cmd` onto
:data:`~vaultspec_core.cli.spec_cmd_app.spec_app`. A hook binds an agent-runtime
event - a tool call, a session boundary - to a shell command, authored once in
``.vaultspec/hooks/`` and rendered by :mod:`vaultspec_core.core.provider_hooks`
into each installed provider's own config.

Hooks are authored as files, like rules and skills, so this group reads and
renders rather than scaffolding: there is no ``add`` or ``edit``. Distinct from
:mod:`.spec_cmd_triggers`, which fires vaultspec's own lifecycle events, and
from :mod:`.spec_cmd_git`, which manages the git pre-commit boundary. Until
these three were separated, ``spec hooks`` reached the lifecycle system; the
aliases at the foot of this module carry those callers over for one release.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

import typer

from vaultspec_core.cli._app import make_app
from vaultspec_core.cli._errors import handle_error as _handle_error
from vaultspec_core.cli._target import TargetOption, apply_target
from vaultspec_core.cli.spec_cmd_shared import (
    apply_provider_filter,
    emit_json,
    emit_sync_result,
)

if TYPE_CHECKING:
    from vaultspec_core.core.provider_hooks import HookSpec

hooks_app = make_app(
    help="Render shell commands into each provider's agent-runtime hook config",
    no_args_is_help=True,
)


def _load(warnings: list[str] | None = None) -> list[HookSpec]:
    """Load this workspace's hook specs."""
    from vaultspec_core.core.provider_hooks import load_provider_hook_specs

    return load_provider_hook_specs(warnings=warnings)


@hooks_app.command("list")
def cmd_hooks_list(
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """List this workspace's hooks and the providers they render into."""
    apply_target(target)
    from vaultspec_core.core.provider_hooks import hook_targets, supported_events
    from vaultspec_core.core.types import get_context

    specs = _load()
    targets = hook_targets()
    hooks_dir = str(get_context().hooks_dir)
    provider_names = [tool.value for tool, _n, _s in targets]

    def _renders_into(spec: HookSpec) -> list[str]:
        return [
            tool.value
            for tool, _n, _s in targets
            if spec.event in supported_events(tool)
        ]

    if json_output:
        emit_json(
            "spec.hooks.list",
            "unchanged",
            {
                "hooks": [
                    {
                        "name": spec.name,
                        "event": spec.event.value,
                        "matcher": spec.matcher,
                        "enabled": spec.enabled,
                        "timeout": spec.timeout,
                        "providers": _renders_into(spec),
                    }
                    for spec in specs
                ],
                "hooks_dir": hooks_dir,
                "providers": provider_names,
            },
        )
        raise typer.Exit(0)

    from vaultspec_core.cli.rendering import Cell, Column, render_listing, summary_line
    from vaultspec_core.console import get_console

    console = get_console()
    if not specs:
        console.print("No hooks defined.")
        console.print(f"  Add [dim].yaml[/dim] files to [bold]{hooks_dir}/[/bold]")
        return

    rows: list[dict[str, object]] = [
        {
            "name": spec.name,
            "status": Cell("enabled", style="bold green")
            if spec.enabled
            else Cell("disabled", style="dim"),
            "event": spec.event.value,
            "matcher": spec.matcher or "-",
            "providers": ", ".join(_renders_into(spec)) or Cell("none", style="yellow"),
        }
        for spec in specs
    ]
    render_listing(
        rows,
        columns=[
            Column("name"),
            Column("status"),
            Column("event"),
            Column("matcher"),
            Column("providers"),
        ],
        title="hooks",
    )
    console.print(summary_line(len(rows), "hook"))


@hooks_app.command("show")
def cmd_hooks_show(
    name: Annotated[str, typer.Argument(help="Hook name")],
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Show one hook's source file."""
    apply_target(target)
    from vaultspec_core.core.exceptions import ResourceNotFoundError
    from vaultspec_core.core.types import get_context

    hooks_dir = get_context().hooks_dir
    for candidate in (hooks_dir / f"{name}.yaml", hooks_dir / f"{name}.yml"):
        if candidate.exists():
            content = candidate.read_text(encoding="utf-8")
            break
    else:
        _handle_error(
            ResourceNotFoundError(f"Hook '{name}' not found."),
            json_output=json_output,
        )
        return

    if json_output:
        emit_json("spec.hooks.show", "unchanged", {"name": name, "content": content})
        raise typer.Exit(0)

    typer.echo(content)


@hooks_app.command("status")
def cmd_hooks_status(
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Report parse errors and events no installed provider can run."""
    apply_target(target)
    from vaultspec_core.core.provider_hooks import (
        hook_targets,
        render_hooks_payload,
        supported_events,
    )
    from vaultspec_core.core.types import get_context

    warnings: list[str] = []
    specs = _load(warnings)
    targets = hook_targets()

    # A spec no installed provider can run is the failure this surface exists
    # for: it parses, it looks authored, and it silently never fires anywhere.
    for spec in specs:
        if not spec.enabled:
            continue
        if not any(spec.event in supported_events(tool) for tool, _n, _s in targets):
            warnings.append(
                f"Hook {spec.name!r}: no installed provider supports event "
                f"{spec.event.value!r}; it renders nowhere."
            )
    for tool, _native, _sidecar in targets:
        render_hooks_payload(specs, tool, warnings)

    status = "warning" if warnings else "ok"
    hooks_dir = str(get_context().hooks_dir)
    definitions = [spec.name for spec in specs]
    provider_names = [tool.value for tool, _n, _s in targets]

    if json_output:
        emit_json(
            "spec.hooks.status",
            status,
            {
                "status": status,
                "hooks_dir": hooks_dir,
                "definitions": definitions,
                "warnings": warnings,
                "providers": provider_names,
            },
        )
        raise typer.Exit(0 if status == "ok" else 1)

    from vaultspec_core.cli.rendering import Field, render_record
    from vaultspec_core.console import get_console

    render_record(
        [
            Field("status", status, style="green" if status == "ok" else "yellow"),
            Field("hooks_dir", hooks_dir),
            Field("definitions", ", ".join(definitions) or "none"),
            Field("providers", ", ".join(provider_names) or "none"),
        ],
        title="hooks status",
    )
    console = get_console()
    for warning in warnings:
        console.print(f"  [yellow]-[/yellow] {warning}")
    if status != "ok":
        raise typer.Exit(code=1)


@hooks_app.command("sync")
def cmd_hooks_sync(
    provider: Annotated[
        str,
        typer.Argument(
            help="Provider to sync (all, claude, gemini, antigravity, codex)"
        ),
    ] = "all",
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview changes")] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Render this workspace's hooks into each provider's native config."""
    apply_target(target)
    apply_provider_filter(provider)
    from vaultspec_core.core.provider_hooks import provider_hooks_sync

    result = provider_hooks_sync(dry_run=dry_run)
    emit_sync_result(result, label="Hooks", dry_run=dry_run, json_output=json_output)


def _note_separate_trigger_grants(json_output: bool) -> None:
    """Warn when this workspace also has ungranted lifecycle triggers.

    ``spec hooks trust`` is the one verb the split changed the meaning of, and
    the only one with no deprecation alias to say so: before the split it
    approved lifecycle triggers, and it now approves provider hooks. An
    operator restoring grants the upgrade migration dropped will type the verb
    they have always typed, and would otherwise approve a different set of
    commands over a different directory - one that runs inside their agent's
    session on every matching tool call - believing they had restored the old
    one. ``add`` and ``run`` print a deprecation line; this stands in for it.
    """
    if json_output:
        return
    from vaultspec_core.core.types import get_context
    from vaultspec_core.triggers import load_triggers, partition_by_trust

    try:
        triggers = load_triggers(get_context().triggers_dir)
    except Exception:
        return
    _trusted, untrusted = partition_by_trust(triggers)
    if not untrusted:
        return

    from vaultspec_core.console import get_console

    get_console().print(
        f"[yellow]note:[/yellow] this workspace also has {len(untrusted)} "
        "unapproved lifecycle trigger(s). They are approved separately with "
        "[bold]vaultspec-core spec triggers trust[/bold]; this command "
        "approves provider hooks only."
    )


@hooks_app.command("trust")
def cmd_hooks_trust(
    name: Annotated[str | None, typer.Argument(help="Hook name")] = None,
    revoke: Annotated[
        bool,
        typer.Option("--revoke", help="Withdraw approval for this workspace's hooks"),
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Approve this workspace's hooks to be rendered into your agents' configs.

    Hook files are shared through git, so a checkout arrives carrying commands
    its author chose - and a rendered hook runs inside your agent's session on
    every matching tool call, not once per sync. Approval is therefore recorded
    on this machine rather than in the workspace, and is pinned to each file's
    current contents: editing an approved hook, or pulling a change to one,
    withdraws the approval until you run this again. Use --revoke to withdraw it
    yourself; the next sync then removes what it had rendered.
    """
    apply_target(target)
    from vaultspec_core.core.exceptions import ResourceNotFoundError
    from vaultspec_core.core.types import get_context
    from vaultspec_core.triggers import grant
    from vaultspec_core.triggers import revoke as revoke_trust

    _note_separate_trigger_grants(json_output)
    hooks_dir = get_context().hooks_dir

    if revoke:
        dropped = revoke_trust(hooks_dir)
        if json_output:
            emit_json("spec.hooks.trust", "removed", {"revoked": dropped})
            raise typer.Exit(0)
        from vaultspec_core.console import get_console

        get_console().print(f"Withdrew approval for {dropped} hook(s).")
        return

    specs = _load()
    if name is not None:
        specs = [spec for spec in specs if spec.name == name]
        if not specs:
            _handle_error(
                ResourceNotFoundError(f"Hook '{name}' not found."),
                json_output=json_output,
            )
            return

    paths = [
        path
        for spec in specs
        for path in (hooks_dir / f"{spec.name}.yaml", hooks_dir / f"{spec.name}.yml")
        if path.exists()
    ]
    recorded = grant(paths)
    approved = sorted(path.name for path in recorded)

    if json_output:
        emit_json("spec.hooks.trust", "updated", {"trusted": approved})
        raise typer.Exit(0)

    from vaultspec_core.console import get_console

    console = get_console()
    if not approved:
        console.print("No hooks to approve.")
        return
    console.print(f"Approved {len(approved)} hook(s) in {hooks_dir}:")
    for entry in approved:
        console.print(f"  {entry}")
    console.print(
        "[dim]Approval is recorded on this machine and pinned to each file's "
        "contents; editing a hook asks again.[/dim]"
    )


# =============================================================================
# Deprecated aliases
# =============================================================================
#
# ``spec hooks add|run|trust`` reached the lifecycle system before the split.
# They stay for one release so a scripted caller gets a message rather than a
# silent change of meaning, and they delegate to the triggers implementation -
# which is what such a caller meant - rather than to the hook verbs that now
# own those names. ``trust`` is the exception in reverse: this module defines a
# real ``trust`` above, so only ``add`` and ``run`` can be aliased here, and
# ``spec hooks trust`` now grants for hooks. That change of meaning is the one
# an operator is told about by the deprecation line on the other two.
#
# Listed rather than hidden. The documentation contract is that every command
# the docs name is a command the CLI shows, and a deprecation nobody can
# discover is a worse deprecation: the operator reading ``--help`` to find out
# where ``add`` went is exactly who needs to be told.


def _deprecated(verb: str) -> None:
    typer.echo(
        f"warning: 'spec hooks {verb}' is deprecated and will be removed; "
        f"use 'spec triggers {verb}'.",
        err=True,
    )


@hooks_app.command("add")
def cmd_hooks_add_alias(
    name: Annotated[str, typer.Argument(help="Trigger name")],
    event: Annotated[str, typer.Option("--event", help="Lifecycle event")] = (
        "config.synced"
    ),
    command: Annotated[str, typer.Option("--command", help="Shell command")] = "",
    force: Annotated[bool, typer.Option("--force", help="Overwrite")] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Deprecated - use 'spec triggers add'; this alias goes next release."""
    _deprecated("add")
    from vaultspec_core.cli.spec_cmd_triggers import cmd_triggers_add

    cmd_triggers_add(
        name=name,
        event=event,
        command=command,
        force=force,
        json_output=json_output,
        target=target,
    )


@hooks_app.command("run")
def cmd_hooks_run_alias(
    event: Annotated[str, typer.Argument(help="Lifecycle event")],
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Deprecated - use 'spec triggers run'; this alias goes next release."""
    _deprecated("run")
    from vaultspec_core.cli.spec_cmd_triggers import cmd_triggers_run

    cmd_triggers_run(event=event, json_output=json_output, target=target)
