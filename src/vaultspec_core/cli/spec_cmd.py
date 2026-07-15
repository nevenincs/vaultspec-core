"""Spec command group  - manage framework resources in ``.vaultspec/``.

Sub-groups: ``vaultspec-core spec rules`` (:data:`rules_app`),
``vaultspec-core spec skills`` (:data:`skills_app`),
``vaultspec-core spec agents`` (:data:`agents_app`),
``vaultspec-core spec system`` (:data:`system_app`),
``vaultspec-core spec hooks`` (:data:`hooks_app`), and
``vaultspec-core spec mcps`` (:data:`mcps_app`).
Top-level command: ``vaultspec-core spec doctor`` for workspace health diagnosis.
Delegates to :mod:`vaultspec_core.core`
CRUD functions via lazy imports to avoid circular-import issues. Mounted onto
:data:`.root.app` as the ``spec`` command group.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

from vaultspec_core.cli._app import make_app

if TYPE_CHECKING:
    from vaultspec_core.core.diagnosis import ProviderDiagnosis, WorkspaceDiagnosis
    from vaultspec_core.core.types import SyncResult

from vaultspec_core.cli._errors import handle_error as _handle_error
from vaultspec_core.cli._target import TargetOption, apply_target

logger = logging.getLogger(__name__)

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
    from vaultspec_core.cli.rendering import emit_outcomes, sync_outcomes

    outcomes = []
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


def _emit_json(command: str, status: str, data: dict) -> None:
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
    missing, drifted, stale, up_to_date, skipped = [], [], [], [], []
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


spec_app = make_app(
    help=(
        "Manage framework resources: rules, skills, agents, system prompts, hooks, "
        "and MCPs."
    ),
    no_args_is_help=True,
)


# =============================================================================
# Rules
# =============================================================================

rules_app = make_app(
    help="Manage framework rule sources and synced rule outputs",
    no_args_is_help=True,
)
spec_app.add_typer(rules_app, name="rules")


@rules_app.command("list")
def cmd_rules_list(
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """List all available rules."""
    apply_target(target)
    from vaultspec_core.core import rules_list

    items = rules_list()

    if json_output:
        _emit_json("spec.rules.list", "unchanged", {"items": items})
        raise typer.Exit(0)

    from vaultspec_core.cli.rendering import Column, render_listing, summary_line

    rows = [{"name": item["name"], "source": item["source"]} for item in items]
    render_listing(
        rows,
        [Column("name"), Column("source")],
        title="rules",
        summary=summary_line(len(rows), "rules"),
        empty="no rules",
    )


@rules_app.command("add")
def cmd_rules_add(
    name: Annotated[str, typer.Argument(help="Rule name")],
    body: Annotated[
        str | None, typer.Option("--body", help="Rule body content")
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
    """Add a new custom rule source under .vaultspec/."""
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

    from vaultspec_core.core import rules_add
    from vaultspec_core.core.exceptions import VaultSpecError

    try:
        file_path = rules_add(
            name=name, content=resolved_body, force=force, dry_run=dry_run
        )
    except VaultSpecError as exc:
        _handle_error(exc, json_output=json_output)
        return

    if json_output:
        _emit_json("spec.rules.add", "created", {"path": str(file_path)})
        raise typer.Exit(0)

    action = "Would create rule source" if dry_run else "Rule source updated"
    _print_source_mutation_notice(file_path, action=action)


@rules_app.command("show")
def cmd_rules_show(
    name: Annotated[str, typer.Argument(help="Rule name")],
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Display a rule's content."""
    apply_target(target)
    from vaultspec_core.core import resource_show
    from vaultspec_core.core.exceptions import VaultSpecError
    from vaultspec_core.core.types import get_context

    try:
        content = resource_show(
            name=name, base_dir=get_context().rules_src_dir, label="Rule"
        )
        if json_output:
            _emit_json(
                "spec.rules.show", "unchanged", {"name": name, "content": content}
            )
            raise typer.Exit(0)
        typer.echo(content)
    except (VaultSpecError, OSError) as exc:
        _handle_error(exc, json_output=json_output)


@rules_app.command("edit")
def cmd_rules_edit(
    name: Annotated[str, typer.Argument(help="Rule name")],
    editor: Annotated[
        str | None, typer.Option("--editor", help="Override the editor binary to use")
    ] = None,
    target: TargetOption = None,
) -> None:
    """Open a rule in the configured editor.

    Editor resolution order:
      1. Command-line --editor flag
      2. Project-local config (vaultspec-core config set editor <value>)
      3. $VISUAL environment variable
      4. $EDITOR environment variable
      5. Fallback to 'vi'

    If no working editor is resolved, the command exits with code 2.
    """
    apply_target(target)
    from vaultspec_core.core.types import get_context

    _run_edit_command(
        name=name,
        base_dir=get_context().rules_src_dir,
        label="Rule",
        is_dir=False,
        editor=editor,
    )


@rules_app.command("remove")
def cmd_rules_remove(
    name: Annotated[str, typer.Argument(help="Rule name")],
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
    """Delete a rule."""
    apply_target(target)
    from vaultspec_core.core import resource_remove
    from vaultspec_core.core.exceptions import VaultSpecError
    from vaultspec_core.core.types import get_context

    try:
        resource_remove(
            name=name,
            base_dir=get_context().rules_src_dir,
            label="Rule",
            force=force,
            confirm_fn=typer.confirm,
        )
    except (VaultSpecError, OSError) as exc:
        _handle_error(exc, json_output=json_output)
        return

    if json_output:
        _emit_json("spec.rules.remove", "removed", {"removed": name})
        raise typer.Exit(0)

    _print_source_mutation_notice(
        _resource_path(get_context().rules_src_dir, name),
        action="Rule source removed",
    )


@rules_app.command("rename")
def cmd_rules_rename(
    old_name: Annotated[str, typer.Argument(help="Current rule name")],
    new_name: Annotated[str, typer.Argument(help="New rule name")],
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Rename an existing rule atomically.

    Rewrites both filename and frontmatter name.
    """
    apply_target(target)
    from vaultspec_core.core import resource_rename
    from vaultspec_core.core.exceptions import VaultSpecError
    from vaultspec_core.core.types import get_context

    try:
        new_path = resource_rename(
            old_name=old_name,
            new_name=new_name,
            base_dir=get_context().rules_src_dir,
            label="Rule",
        )
    except (VaultSpecError, OSError) as exc:
        _handle_error(exc, json_output=json_output)
        return

    if json_output:
        _emit_json(
            "spec.rules.rename",
            "updated",
            {"old_name": old_name, "new_name": new_name, "path": str(new_path)},
        )
        raise typer.Exit(0)

    _print_source_mutation_notice(new_path, action="Rule source renamed")


@rules_app.command("sync")
def cmd_rules_sync(
    provider: Annotated[
        str,
        typer.Argument(
            help="Provider to sync (all, claude, gemini, antigravity, codex)"
        ),
    ] = "all",
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview changes")] = False,
    force: Annotated[
        bool,
        typer.Option("--force", help="Prune stale files and overwrite user content"),
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Sync only rule files; use vaultspec-core sync for complete refresh."""
    apply_target(target)
    _apply_provider_filter(provider)
    from vaultspec_core.core import rules_sync

    result = rules_sync(prune=force, dry_run=dry_run)

    if not json_output:
        _print_complete_sync_notice(resource="rule")
    _emit_sync_result(result, label="Rules", dry_run=dry_run, json_output=json_output)


@rules_app.command("restore")
def cmd_rules_restore(
    filename: Annotated[str, typer.Argument(help="Rule name or filename to restore")],
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Restore a rule to its snapshotted original."""
    apply_target(target)
    _restore_resource_command(
        category="rules", label="rule", filename=filename, json_output=json_output
    )


@rules_app.command("status")
def cmd_rules_status(
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Report rules sync status against provider destinations."""
    apply_target(target)
    from vaultspec_core.core import rules_sync

    result = rules_sync(prune=True, dry_run=True)
    _spec_status_command(result, label="Rules", json_output=json_output)


# =============================================================================
# Skills
# =============================================================================

skills_app = make_app(
    help="Manage workflow skills and synced skill outputs",
    no_args_is_help=True,
)
spec_app.add_typer(skills_app, name="skills")


@skills_app.command("list")
def cmd_skills_list(
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """List all available skills."""
    apply_target(target)
    from vaultspec_core.core import skills_list

    items = skills_list()

    if json_output:
        _emit_json("spec.skills.list", "unchanged", {"items": items})
        raise typer.Exit(0)

    from vaultspec_core.cli.rendering import (
        Column,
        render_listing,
        summary_line,
        truncate,
    )

    rows = [
        {"name": item["name"], "description": truncate(item["description"], 60)}
        for item in items
    ]
    render_listing(
        rows,
        [Column("name"), Column("description")],
        title="skills",
        summary=summary_line(len(rows), "skills"),
        empty="no skills",
    )


@skills_app.command("add")
def cmd_skills_add(
    name: Annotated[str, typer.Argument(help="Skill name")],
    description: Annotated[
        str, typer.Option("--description", help="Skill description")
    ] = "",
    body: Annotated[
        str | None, typer.Option("--body", help="Skill body content")
    ] = None,
    from_file: Annotated[
        Path | None, typer.Option("--from-file", help="Read body content from file")
    ] = None,
    force: Annotated[bool, typer.Option("--force", help="Overwrite existing")] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Preview without writing")
    ] = False,
    template: Annotated[
        str | None, typer.Option("--template", help="Template to use")
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Add a new skill."""
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

    from vaultspec_core.core import skills_add
    from vaultspec_core.core.exceptions import VaultSpecError

    try:
        file_path = skills_add(
            name=name,
            description=description,
            force=force,
            template=template,
            body=resolved_body,
            dry_run=dry_run,
        )
    except VaultSpecError as exc:
        _handle_error(exc, json_output=json_output)
        return

    if json_output:
        _emit_json("spec.skills.add", "created", {"path": str(file_path)})
        raise typer.Exit(0)

    action = "Would create skill source" if dry_run else "Skill source updated"
    _print_source_mutation_notice(file_path, action=action)


@skills_app.command("show")
def cmd_skills_show(
    name: Annotated[str, typer.Argument(help="Skill name")],
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Display a skill's content."""
    apply_target(target)
    from vaultspec_core.core import resource_show
    from vaultspec_core.core.exceptions import VaultSpecError
    from vaultspec_core.core.types import get_context

    try:
        content = resource_show(
            name=name, base_dir=get_context().skills_src_dir, label="Skill", is_dir=True
        )
        if json_output:
            _emit_json(
                "spec.skills.show", "unchanged", {"name": name, "content": content}
            )
            raise typer.Exit(0)
        typer.echo(content)
    except (VaultSpecError, OSError) as exc:
        _handle_error(exc, json_output=json_output)


@skills_app.command("edit")
def cmd_skills_edit(
    name: Annotated[str, typer.Argument(help="Skill name")],
    editor: Annotated[
        str | None, typer.Option("--editor", help="Override the editor binary to use")
    ] = None,
    target: TargetOption = None,
) -> None:
    """Open a skill in the configured editor.

    Editor resolution order:
      1. Command-line --editor flag
      2. Project-local config (vaultspec-core config set editor <value>)
      3. $VISUAL environment variable
      4. $EDITOR environment variable
      5. Fallback to 'vi'

    If no working editor is resolved, the command exits with code 2.
    """
    apply_target(target)
    from vaultspec_core.core.types import get_context

    _run_edit_command(
        name=name,
        base_dir=get_context().skills_src_dir,
        label="Skill",
        is_dir=True,
        editor=editor,
    )


@skills_app.command("remove")
def cmd_skills_remove(
    name: Annotated[str, typer.Argument(help="Skill name")],
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
    """Delete a skill."""
    apply_target(target)
    from vaultspec_core.core import resource_remove
    from vaultspec_core.core.exceptions import VaultSpecError
    from vaultspec_core.core.types import get_context

    try:
        resource_remove(
            name=name,
            base_dir=get_context().skills_src_dir,
            label="Skill",
            force=force,
            is_dir=True,
            confirm_fn=typer.confirm,
        )
    except (VaultSpecError, OSError) as exc:
        _handle_error(exc, json_output=json_output)
        return

    if json_output:
        _emit_json("spec.skills.remove", "removed", {"removed": name})
        raise typer.Exit(0)

    _print_source_mutation_notice(
        get_context().skills_src_dir / name,
        action="Skill source removed",
    )


@skills_app.command("rename")
def cmd_skills_rename(
    old_name: Annotated[str, typer.Argument(help="Current skill name")],
    new_name: Annotated[str, typer.Argument(help="New skill name")],
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Rename an existing skill atomically.

    Rewrites both directory name and SKILL.md frontmatter name.
    """
    apply_target(target)
    from vaultspec_core.core import resource_rename
    from vaultspec_core.core.exceptions import VaultSpecError
    from vaultspec_core.core.types import get_context

    try:
        new_path = resource_rename(
            old_name=old_name,
            new_name=new_name,
            base_dir=get_context().skills_src_dir,
            label="Skill",
            is_dir=True,
        )
    except (VaultSpecError, OSError) as exc:
        _handle_error(exc, json_output=json_output)
        return

    if json_output:
        _emit_json(
            "spec.skills.rename",
            "updated",
            {"old_name": old_name, "new_name": new_name, "path": str(new_path)},
        )
        raise typer.Exit(0)

    _print_source_mutation_notice(new_path, action="Skill source renamed")


@skills_app.command("sync")
def cmd_skills_sync(
    provider: Annotated[
        str,
        typer.Argument(
            help="Provider to sync (all, claude, gemini, antigravity, codex)"
        ),
    ] = "all",
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview changes")] = False,
    force: Annotated[
        bool,
        typer.Option("--force", help="Prune stale files and overwrite user content"),
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Sync only skill files; use vaultspec-core sync for complete refresh."""
    apply_target(target)
    _apply_provider_filter(provider)
    from vaultspec_core.core import skills_sync

    result = skills_sync(prune=force, dry_run=dry_run)

    if not json_output:
        _print_complete_sync_notice(resource="skill")
    _emit_sync_result(result, label="Skills", dry_run=dry_run, json_output=json_output)


@skills_app.command("restore")
def cmd_skills_restore(
    filename: Annotated[str, typer.Argument(help="Skill name or filename to restore")],
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Restore a skill to its snapshotted original."""
    apply_target(target)
    _restore_resource_command(
        category="skills", label="skill", filename=filename, json_output=json_output
    )


@skills_app.command("status")
def cmd_skills_status(
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Report skills sync status against provider destinations."""
    apply_target(target)
    from vaultspec_core.core import skills_sync

    result = skills_sync(prune=True, dry_run=True)
    _spec_status_command(result, label="Skills", json_output=json_output)


# =============================================================================
# Agents
# =============================================================================

agents_app = make_app(
    help="Manage agent definitions and synced agent outputs",
    no_args_is_help=True,
)
spec_app.add_typer(agents_app, name="agents")


@agents_app.command("list")
def cmd_agents_list(
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """List all available agents."""
    apply_target(target)
    from vaultspec_core.core import agents_list

    items = agents_list()

    if json_output:
        _emit_json("spec.agents.list", "unchanged", {"items": items})
        raise typer.Exit(0)

    from vaultspec_core.cli.rendering import (
        Column,
        render_listing,
        summary_line,
        truncate,
    )

    rows = [
        {"name": item["name"], "description": truncate(item["description"], 50)}
        for item in items
    ]
    render_listing(
        rows,
        [Column("name"), Column("description")],
        title="agents",
        summary=summary_line(len(rows), "agents"),
        empty="no agents",
    )


@agents_app.command("add")
def cmd_agents_add(
    name: Annotated[str, typer.Argument(help="Agent name")],
    description: Annotated[
        str, typer.Option("--description", help="Agent description")
    ] = "",
    body: Annotated[
        str | None, typer.Option("--body", help="Agent body content")
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
    """Add a new agent definition."""
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

    from vaultspec_core.core import agents_add
    from vaultspec_core.core.exceptions import VaultSpecError

    try:
        file_path = agents_add(
            name=name,
            description=description,
            force=force,
            body=resolved_body,
            dry_run=dry_run,
        )
    except VaultSpecError as exc:
        _handle_error(exc, json_output=json_output)
        return

    if json_output:
        _emit_json("spec.agents.add", "created", {"path": str(file_path)})
        raise typer.Exit(0)

    action = "Would create agent source" if dry_run else "Agent source updated"
    _print_source_mutation_notice(file_path, action=action)


@agents_app.command("show")
def cmd_agents_show(
    name: Annotated[str, typer.Argument(help="Agent name")],
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Display an agent's content."""
    apply_target(target)
    from vaultspec_core.core import resource_show
    from vaultspec_core.core.exceptions import VaultSpecError
    from vaultspec_core.core.types import get_context

    try:
        content = resource_show(
            name=name, base_dir=get_context().agents_src_dir, label="Agent"
        )
        if json_output:
            _emit_json(
                "spec.agents.show", "unchanged", {"name": name, "content": content}
            )
            raise typer.Exit(0)
        typer.echo(content)
    except (VaultSpecError, OSError) as exc:
        _handle_error(exc, json_output=json_output)


@agents_app.command("edit")
def cmd_agents_edit(
    name: Annotated[str, typer.Argument(help="Agent name")],
    editor: Annotated[
        str | None, typer.Option("--editor", help="Override the editor binary to use")
    ] = None,
    target: TargetOption = None,
) -> None:
    """Open an agent in the configured editor.

    Editor resolution order:
      1. Command-line --editor flag
      2. Project-local config (vaultspec-core config set editor <value>)
      3. $VISUAL environment variable
      4. $EDITOR environment variable
      5. Fallback to 'vi'

    If no working editor is resolved, the command exits with code 2.
    """
    apply_target(target)
    from vaultspec_core.core.types import get_context

    _run_edit_command(
        name=name,
        base_dir=get_context().agents_src_dir,
        label="Agent",
        is_dir=False,
        editor=editor,
    )


@agents_app.command("remove")
def cmd_agents_remove(
    name: Annotated[str, typer.Argument(help="Agent name")],
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
    """Delete an agent definition."""
    apply_target(target)
    from vaultspec_core.core import resource_remove
    from vaultspec_core.core.exceptions import VaultSpecError
    from vaultspec_core.core.types import get_context

    try:
        resource_remove(
            name=name,
            base_dir=get_context().agents_src_dir,
            label="Agent",
            force=force,
            confirm_fn=typer.confirm,
        )
    except (VaultSpecError, OSError) as exc:
        _handle_error(exc, json_output=json_output)
        return

    if json_output:
        _emit_json("spec.agents.remove", "removed", {"removed": name})
        raise typer.Exit(0)

    _print_source_mutation_notice(
        _resource_path(get_context().agents_src_dir, name),
        action="Agent source removed",
    )


@agents_app.command("rename")
def cmd_agents_rename(
    old_name: Annotated[str, typer.Argument(help="Current agent name")],
    new_name: Annotated[str, typer.Argument(help="New agent name")],
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Rename an existing agent definition atomically.

    Rewrites both filename and frontmatter name.
    """
    apply_target(target)
    from vaultspec_core.core import resource_rename
    from vaultspec_core.core.exceptions import VaultSpecError
    from vaultspec_core.core.types import get_context

    try:
        new_path = resource_rename(
            old_name=old_name,
            new_name=new_name,
            base_dir=get_context().agents_src_dir,
            label="Agent",
        )
    except (VaultSpecError, OSError) as exc:
        _handle_error(exc, json_output=json_output)
        return

    if json_output:
        _emit_json(
            "spec.agents.rename",
            "updated",
            {"old_name": old_name, "new_name": new_name, "path": str(new_path)},
        )
        raise typer.Exit(0)

    _print_source_mutation_notice(new_path, action="Agent source renamed")


@agents_app.command("sync")
def cmd_agents_sync(
    provider: Annotated[
        str,
        typer.Argument(
            help="Provider to sync (all, claude, gemini, antigravity, codex)"
        ),
    ] = "all",
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview changes")] = False,
    force: Annotated[
        bool,
        typer.Option("--force", help="Prune stale files and overwrite user content"),
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Sync only agent files; use vaultspec-core sync for complete refresh."""
    apply_target(target)
    _apply_provider_filter(provider)
    from vaultspec_core.core import agents_sync

    result = agents_sync(prune=force, dry_run=dry_run)

    if not json_output:
        _print_complete_sync_notice(resource="agent")
    _emit_sync_result(result, label="Agents", dry_run=dry_run, json_output=json_output)


@agents_app.command("restore")
def cmd_agents_restore(
    filename: Annotated[str, typer.Argument(help="Agent name or filename to restore")],
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Restore an agent to its snapshotted original."""
    apply_target(target)
    _restore_resource_command(
        category="agents", label="agent", filename=filename, json_output=json_output
    )


@agents_app.command("status")
def cmd_agents_status(
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Report agents sync status against provider destinations."""
    apply_target(target)
    from vaultspec_core.core import agents_sync

    result = agents_sync(prune=True, dry_run=True)
    _spec_status_command(result, label="Agents", json_output=json_output)


# =============================================================================
# System
# =============================================================================

system_app = make_app(
    help="Inspect and sync assembled system prompt outputs",
    no_args_is_help=True,
)
spec_app.add_typer(system_app, name="system")


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
        _emit_json("spec.system.show", "unchanged", data)
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
    _apply_provider_filter(provider)
    from vaultspec_core.core import system_sync

    result = system_sync(dry_run=dry_run, force=force)

    if not json_output:
        _print_complete_sync_notice(resource="system prompt")
    _emit_sync_result(result, label="System", dry_run=dry_run, json_output=json_output)


# =============================================================================
# Hooks
# =============================================================================

hooks_app = make_app(
    help="List and run shell-based workspace hooks",
    no_args_is_help=True,
)
spec_app.add_typer(hooks_app, name="hooks")


@hooks_app.command("list")
def cmd_hooks_list(
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """List all defined hooks."""
    apply_target(target)
    from vaultspec_core.core.commands import hooks_list_data

    data = hooks_list_data()

    if json_output:
        _emit_json("spec.hooks.list", "unchanged", data)
        raise typer.Exit(0)

    from vaultspec_core.cli.rendering import Cell, Column, render_listing, summary_line
    from vaultspec_core.console import get_console

    hooks = data["hooks"]
    console = get_console()

    if not hooks:
        console.print("No hooks defined.")
        console.print(
            f"  Add [dim].yaml[/dim] files to [bold]{data['hooks_dir']}/[/bold]"
        )
        console.print(
            "\n[dim]Supported events:[/dim] " + ", ".join(data["supported_events"])
        )
        return

    rows = [
        {
            "name": hook["name"],
            "status": Cell("enabled", style="bold green")
            if hook["enabled"]
            else Cell("disabled", style="dim"),
            "event": hook["event"],
            "actions": hook["actions"],
        }
        for hook in hooks
    ]
    render_listing(
        rows,
        [Column("name"), Column("status"), Column("event"), Column("actions")],
        title="hooks",
        summary=summary_line(len(rows), "hooks"),
        empty="no hooks",
    )


@hooks_app.command("add")
def cmd_hooks_add(
    name: Annotated[str, typer.Argument(help="Hook name")],
    event: Annotated[
        str, typer.Option("--event", help="Lifecycle event to trigger on")
    ] = "vault.document.created",
    command: Annotated[str, typer.Option("--command", help="Command to run")] = "",
    body: Annotated[
        str | None, typer.Option("--body", help="Hook body content")
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
    """Add a new declarative hook under .vaultspec/."""
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

    from vaultspec_core.core import hooks_add
    from vaultspec_core.core.exceptions import VaultSpecError

    try:
        file_path = hooks_add(
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
        _emit_json("spec.hooks.add", "created", {"path": str(file_path)})
        raise typer.Exit(0)

    action = "Would create hook source" if dry_run else "Hook source updated"
    _print_source_mutation_notice(file_path, action=action)


@hooks_app.command("show")
def cmd_hooks_show(
    name: Annotated[str, typer.Argument(help="Hook name")],
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Display a hook's content."""
    apply_target(target)
    from vaultspec_core.core import hooks_show
    from vaultspec_core.core.exceptions import VaultSpecError

    try:
        content = hooks_show(name=name)
        if json_output:
            _emit_json(
                "spec.hooks.show", "unchanged", {"name": name, "content": content}
            )
            raise typer.Exit(0)
        typer.echo(content)
    except (VaultSpecError, OSError) as exc:
        _handle_error(exc, json_output=json_output)


@hooks_app.command("edit")
def cmd_hooks_edit(
    name: Annotated[str, typer.Argument(help="Hook name")],
    editor: Annotated[
        str | None, typer.Option("--editor", help="Override the editor binary to use")
    ] = None,
    target: TargetOption = None,
) -> None:
    """Open a hook in the configured editor."""
    apply_target(target)
    from vaultspec_core.core import hooks_edit
    from vaultspec_core.core.exceptions import (
        EditorCancellationError,
        EditorResolutionError,
        EditorSubprocessError,
        VaultSpecError,
    )

    try:
        hooks_edit(name=name, editor=editor)
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


@hooks_app.command("rename")
def cmd_hooks_rename(
    old_name: Annotated[str, typer.Argument(help="Current hook name")],
    new_name: Annotated[str, typer.Argument(help="New hook name")],
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Rename an existing hook atomically."""
    apply_target(target)
    from vaultspec_core.core import hooks_rename
    from vaultspec_core.core.exceptions import VaultSpecError

    try:
        new_path = hooks_rename(old_name=old_name, new_name=new_name)
    except (VaultSpecError, OSError) as exc:
        _handle_error(exc, json_output=json_output)
        return

    if json_output:
        _emit_json(
            "spec.hooks.rename",
            "updated",
            {"old_name": old_name, "new_name": new_name, "path": str(new_path)},
        )
        raise typer.Exit(0)

    _print_source_mutation_notice(new_path, action="Hook source renamed")


@hooks_app.command("remove")
def cmd_hooks_remove(
    name: Annotated[str, typer.Argument(help="Hook name")],
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
    """Delete a hook."""
    apply_target(target)
    from vaultspec_core.core import hooks_remove
    from vaultspec_core.core.exceptions import VaultSpecError

    try:
        hooks_remove(
            name=name,
            force=force,
            confirm_fn=typer.confirm,
        )
    except (VaultSpecError, OSError) as exc:
        _handle_error(exc, json_output=json_output)
        return

    if json_output:
        _emit_json("spec.hooks.remove", "removed", {"removed": name})
        raise typer.Exit(0)

    from vaultspec_core.core.hooks import _resolve_hook_path

    _print_source_mutation_notice(
        _resolve_hook_path(name),
        action="Hook source removed",
    )


@hooks_app.command("restore")
def cmd_hooks_restore(
    filename: Annotated[str, typer.Argument(help="Hook name or filename to restore")],
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Restore a hook to its snapshotted original (not supported for custom hooks)."""
    apply_target(target)
    _ = filename
    if json_output:
        _emit_json(
            "spec.hooks.restore",
            "failed",
            {"message": "Custom hooks cannot be restored"},
        )
        raise typer.Exit(1)
    typer.echo("Error: Custom hooks cannot be restored.", err=True)
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
    force: Annotated[
        bool,
        typer.Option("--force", help="Prune stale files and overwrite user content"),
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Sync only hooks files; use vaultspec-core sync for complete refresh."""
    apply_target(target)
    _apply_provider_filter(provider)
    from vaultspec_core.core import hooks_sync

    result = hooks_sync(prune=force, dry_run=dry_run)

    if not json_output:
        _print_complete_sync_notice(resource="hook")
    _emit_sync_result(result, label="Hooks", dry_run=dry_run, json_output=json_output)


@hooks_app.command("status")
def cmd_hooks_status(
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Report declarative hooks parsing and taxonomy compliance status."""
    apply_target(target)
    from vaultspec_core.core import hooks_status

    status = hooks_status()

    if json_output:
        _emit_json("spec.hooks.status", status["status"], status)
        raise typer.Exit(0 if status["status"] == "ok" else 1)

    from vaultspec_core.cli.rendering import Field, render_record
    from vaultspec_core.console import get_console

    status_str = str(status["status"])
    status_style = (
        "green" if status_str == "ok" else ("yellow" if status_str == "warn" else "red")
    )
    fields = [
        Field("status", status_str, style=status_style),
        Field("hooks_dir", str(status["hooks_dir"])),
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


@hooks_app.command("run")
def cmd_hooks_run(
    event: Annotated[str, typer.Argument(help="Event name")],
    path: Annotated[
        str | None, typer.Option("--path", help="Context path variable")
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Trigger hooks for a specific event."""
    apply_target(target)
    from vaultspec_core.console import get_console
    from vaultspec_core.core.commands import hooks_run
    from vaultspec_core.core.exceptions import VaultSpecError

    try:
        results = hooks_run(event=event, path=path)
    except VaultSpecError as exc:
        _handle_error(exc, json_output=json_output)
        return

    if json_output:
        _emit_json("spec.hooks.run", "unchanged", {"results": results})
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
        console.print(f"  {r['hook_name']} ({r['action_type']}): {icon}")
        if r["output"]:
            for line in str(r["output"]).splitlines()[:5]:
                console.print(f"    {line}")
        if r["error"]:
            console.print(f"    [red]error:[/red] {r['error']}")


# =============================================================================
# MCPs
# =============================================================================

mcps_app = make_app(
    help="Manage canonical MCP definitions and provider-native enrollment.",
    no_args_is_help=True,
)
spec_app.add_typer(mcps_app, name="mcps")


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
        _emit_json("spec.mcps.list", "unchanged", {"items": items})
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
    _apply_provider_filter(provider)
    from vaultspec_core.core import mcp_status

    status = mcp_status(provider=provider, scope=scope)

    if json_output:
        _emit_json("spec.mcps.status", "unchanged", status)
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
        _emit_json("spec.mcps.add", "created", {"path": str(file_path)})
        raise typer.Exit(0)

    _print_source_mutation_notice(file_path, action="MCP source updated")


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
        _emit_json("spec.mcps.remove", "removed", {"removed": name})
        raise typer.Exit(0)

    _print_source_mutation_notice(removed_path, action="MCP source removed")


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
    _apply_provider_filter(provider)
    from vaultspec_core.core import mcp_sync

    result = mcp_sync(
        provider=provider,
        scope=scope,
        force=force,
        prune=prune,
        dry_run=dry_run,
    )

    if not json_output:
        _print_complete_sync_notice(resource="MCP", mcp=True)
    _emit_sync_result(result, label="MCPs", dry_run=dry_run, json_output=json_output)


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
    _apply_provider_filter(provider)
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
    _emit_sync_result(
        result,
        label="MCPs uninstall",
        dry_run=dry_run,
        json_output=json_output,
        command="spec.mcps.uninstall",
    )


# =============================================================================
# Doctor
# =============================================================================


@spec_app.command("doctor")
def cmd_doctor(
    target: TargetOption = None,
    json_output: Annotated[
        bool, typer.Option("--json", help="Output diagnosis as JSON")
    ] = False,
) -> None:
    """Diagnose workspace health and report issues.

    Runs all diagnostic collectors and reports the state of the framework,
    providers, builtins, gitignore, and configuration files.

    Exit codes: 0 = all ok, 1 = warnings, 2 = errors.
    """
    import dataclasses

    from vaultspec_core.core.diagnosis import (
        diagnose,
    )

    effective = target or Path.cwd()
    effective = effective.resolve()

    if not effective.exists():
        typer.echo(
            f"Error: target directory does not exist: {effective}",
            err=True,
        )
        raise typer.Exit(code=2)

    previous_logging_disable = logging.root.manager.disable
    if json_output:
        logging.disable(logging.CRITICAL)
    try:
        # Initialize workspace context so collectors can read tool configs.
        try:
            apply_target(target)
        except Exception:
            logger.debug("Could not initialize workspace context", exc_info=True)

        try:
            diag = diagnose(effective, scope="full")
        except Exception as exc:
            typer.echo(f"Error: diagnosis failed: {exc}", err=True)
            raise typer.Exit(code=2) from None
    finally:
        if json_output:
            logging.disable(previous_logging_disable)

    if json_output:
        data = dataclasses.asdict(diag)
        exit_code = _doctor_exit_code(diag)
        _emit_json("spec.doctor", "failed" if exit_code else "unchanged", data)
        raise typer.Exit(code=exit_code)

    from vaultspec_core.console import get_console

    console = get_console()
    _render_diagnosis_table(console, diag)

    exit_code = _doctor_exit_code(diag)
    raise typer.Exit(code=exit_code)


# =============================================================================
# Reference (generated documentation)
# =============================================================================

reference_app = make_app(
    help="Generate the derivable regions of the bundled CLI reference",
    no_args_is_help=True,
)
spec_app.add_typer(reference_app, name="reference")


@reference_app.command("generate")
def cmd_reference_generate(
    check: Annotated[
        bool,
        typer.Option(
            "--check",
            help=(
                "Render in memory and diff against the committed reference; "
                "exit non-zero on mismatch without writing."
            ),
        ),
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Regenerate the generator-owned regions of the bundled CLI reference.

    The bundled machine-facing reference at
    ``src/vaultspec_core/builtins/reference/cli.md`` carries generator-owned
    zones (delimited by ``vaultspec:generated`` HTML-comment markers) and
    hand-written prose zones. This verb rewrites only the managed zones from
    the live Typer command tree, leaving the prose untouched.

    Default (write) mode rewrites the file in place when the managed regions
    have drifted. ``--check`` mode renders into memory, diffs against the
    committed file, prints the diff, and exits non-zero on mismatch (the CI and
    pre-commit entry point); it exits 0 when the reference is already in sync.
    """
    from vaultspec_core.cli.reference_gen import (
        ReferenceMarkerError,
        generate_all,
    )

    try:
        results = generate_all(check=check)
    except (ReferenceMarkerError, OSError) as exc:
        if json_output:
            _emit_json("spec.reference.generate", "failed", {"message": str(exc)})
        else:
            typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    files = [
        {
            "path": str(result.path),
            "name": result.path.name,
            "in_sync": result.in_sync,
            "changed": result.changed,
            "diff": result.diff,
        }
        for result in results
    ]
    out_of_sync = [result for result in results if result.changed]

    if check:
        if not out_of_sync:
            if json_output:
                _emit_json(
                    "spec.reference.generate",
                    "unchanged",
                    {"files": files, "in_sync": True},
                )
            else:
                names = ", ".join(result.path.name for result in results)
                typer.echo(f"Generated references in sync: {names}.")
            raise typer.Exit(0)
        if json_output:
            _emit_json(
                "spec.reference.generate",
                "failed",
                {"files": files, "in_sync": False},
            )
        else:
            for result in out_of_sync:
                typer.echo(
                    f"Generated reference {result.path.name} is out of sync with "
                    "the live CLI surface.",
                    err=True,
                )
                typer.echo(result.diff, err=True)
            typer.echo(
                "  Run 'vaultspec-core spec reference generate' to refresh it.",
                err=True,
            )
        raise typer.Exit(code=1)

    if not out_of_sync:
        if json_output:
            _emit_json(
                "spec.reference.generate",
                "unchanged",
                {"files": files, "in_sync": True},
            )
        else:
            names = ", ".join(result.path.name for result in results)
            typer.echo(f"Generated references already up to date: {names}.")
        raise typer.Exit(0)

    if json_output:
        _emit_json(
            "spec.reference.generate",
            "updated",
            {"files": files},
        )
    else:
        names = ", ".join(result.path.name for result in out_of_sync)
        typer.echo(f"Regenerated managed regions of: {names}.")
    raise typer.Exit(0)


def _render_diagnosis_table(_console, diag: "WorkspaceDiagnosis") -> None:
    """Render the workspace diagnosis as a box-free listing.

    The ``_console`` argument is retained for call-site compatibility; the
    listing renderer resolves the shared console itself.
    """
    from vaultspec_core.cli.rendering import Cell, Column, render_listing
    from vaultspec_core.core.diagnosis import (
        BuiltinVersionSignal,
        ConfigSignal,
        ContentSignal,
        FrameworkSignal,
        GitattributesSignal,
        GitignoreSignal,
        ManifestEntrySignal,
        ModeMismatchSignal,
        PrecommitSignal,
        RenameIntegritySignal,
        VaultContentSignal,
        VersionFloorSignal,
    )

    rows: list[dict] = []

    # Framework row
    fw_status, fw_style = _signal_status(
        diag.framework,
        {
            FrameworkSignal.PRESENT: ("ok", "green"),
            FrameworkSignal.MISSING: ("error", "red"),
            FrameworkSignal.CORRUPTED: ("error", "red"),
        },
    )
    fw_detail = {
        FrameworkSignal.PRESENT: ".vaultspec/ present",
        FrameworkSignal.MISSING: ".vaultspec/ not found",
        FrameworkSignal.CORRUPTED: ".vaultspec/ corrupted manifest",
    }.get(diag.framework, str(diag.framework))
    rows.append(
        {
            "component": "framework",
            "status": Cell(fw_status, style=fw_style),
            "detail": fw_detail,
        }
    )

    # Provider rows
    for tool, prov in diag.providers.items():
        prov_status, prov_style = _provider_status(prov)
        details = []
        details.append(f"dir: {prov.dir_state.value}")
        if prov.manifest_entry not in (
            ManifestEntrySignal.COHERENT,
            ManifestEntrySignal.NOT_INSTALLED,
        ):
            details.append(f"manifest: {prov.manifest_entry.value}")
        if prov.config not in (ConfigSignal.OK,):
            details.append(f"config: {prov.config.value}")
        stale = sum(1 for s in prov.content.values() if s != ContentSignal.CLEAN)
        if stale:
            details.append(f"{stale} file(s) need attention")
        rows.append(
            {
                "component": tool.value,
                "status": Cell(prov_status, style=prov_style),
                "detail": ", ".join(details),
            }
        )

    # Builtins row
    bv_status, bv_style = _signal_status(
        diag.builtin_version,
        {
            BuiltinVersionSignal.CURRENT: ("ok", "green"),
            BuiltinVersionSignal.MODIFIED: ("warn", "yellow"),
            BuiltinVersionSignal.DELETED: ("error", "red"),
            BuiltinVersionSignal.NO_SNAPSHOTS: ("info", "dim"),
        },
    )
    rows.append(
        {
            "component": "builtins",
            "status": Cell(bv_status, style=bv_style),
            "detail": diag.builtin_version.value,
        }
    )

    # Gitignore row
    gi_status, gi_style = _signal_status(
        diag.gitignore,
        {
            GitignoreSignal.COMPLETE: ("ok", "green"),
            GitignoreSignal.PARTIAL: ("warn", "yellow"),
            GitignoreSignal.NO_ENTRIES: ("info", "dim"),
            GitignoreSignal.NO_FILE: ("info", "dim"),
            GitignoreSignal.CORRUPTED: ("error", "red"),
        },
    )
    rows.append(
        {
            "component": "gitignore",
            "status": Cell(gi_status, style=gi_style),
            "detail": diag.gitignore.value,
        }
    )

    # Gitattributes row
    ga_status, ga_style = _signal_status(
        diag.gitattributes,
        {
            GitattributesSignal.COMPLETE: ("ok", "green"),
            GitattributesSignal.PARTIAL: ("warn", "yellow"),
            GitattributesSignal.NO_ENTRIES: ("info", "dim"),
            GitattributesSignal.NO_FILE: ("info", "dim"),
            GitattributesSignal.CORRUPTED: ("error", "red"),
        },
    )
    rows.append(
        {
            "component": "gitattributes",
            "status": Cell(ga_status, style=ga_style),
            "detail": diag.gitattributes.value,
        }
    )

    # MCP row
    mcp_status, mcp_style = _signal_status(
        diag.mcp,
        {
            ConfigSignal.OK: ("ok", "green"),
            ConfigSignal.MISSING: ("warn", "yellow"),
            ConfigSignal.PARTIAL_MCP: ("info", "dim"),
            ConfigSignal.USER_MCP: ("info", "dim"),
            ConfigSignal.FOREIGN: ("info", "dim"),
            ConfigSignal.REGISTRY_DRIFT: ("warn", "yellow"),
        },
    )
    mcp_detail = {
        ConfigSignal.OK: ".mcp.json present",
        ConfigSignal.MISSING: ".mcp.json not found",
        ConfigSignal.PARTIAL_MCP: ".mcp.json missing or incomplete",
        ConfigSignal.USER_MCP: ".mcp.json includes user-managed entries",
        ConfigSignal.FOREIGN: ".mcp.json present (no vaultspec entry)",
        ConfigSignal.REGISTRY_DRIFT: ".mcp.json entries differ from registry",
    }.get(diag.mcp, str(diag.mcp))
    rows.append(
        {
            "component": "mcp",
            "status": Cell(mcp_status, style=mcp_style),
            "detail": mcp_detail,
        }
    )

    # Migration row - sourced from the registry collector.
    mig_state = diag.migration_status
    if mig_state == "up_to_date":
        mig_status_label, mig_style = ("ok", "green")
        mig_detail = "all registered migrations applied"
    elif mig_state == "pending":
        mig_status_label, mig_style = ("warn", "yellow")
        pending = ", ".join(diag.pending_migrations)
        mig_detail = f"pending: {pending}"
    else:
        mig_status_label, mig_style = ("info", "dim")
        mig_detail = "no manifest; not installed"
    rows.append(
        {
            "component": "migration",
            "status": Cell(mig_status_label, style=mig_style),
            "detail": mig_detail,
        }
    )

    # Vault content row - read-only annotation signal.
    vc_status, vc_style = _signal_status(
        diag.vault_content,
        {
            VaultContentSignal.CLEAN: ("ok", "green"),
            VaultContentSignal.ANNOTATIONS: ("warn", "yellow"),
            VaultContentSignal.UNREADABLE: ("warn", "yellow"),
            VaultContentSignal.NO_VAULT: ("info", "dim"),
        },
    )
    vc_details = {
        VaultContentSignal.CLEAN: "no generated template annotations",
        VaultContentSignal.ANNOTATIONS: (
            f"{diag.vault_annotation_count} document(s) contain generated "
            "template annotations; run vaultspec-core vault sanitize annotations"
        ),
        VaultContentSignal.UNREADABLE: (
            f"{diag.vault_unreadable_count} markdown file(s) unreadable"
        ),
        VaultContentSignal.NO_VAULT: "no vault documents found",
    }
    vc_detail = vc_details.get(diag.vault_content, str(diag.vault_content))
    if (
        diag.vault_content == VaultContentSignal.ANNOTATIONS
        and diag.vault_unreadable_count
    ):
        vc_detail += f"; {diag.vault_unreadable_count} markdown file(s) unreadable"
    rows.append(
        {
            "component": "vault content",
            "status": Cell(vc_status, style=vc_style),
            "detail": vc_detail,
        }
    )

    # Pre-commit row
    pc_status, pc_style = _signal_status(
        diag.precommit,
        {
            PrecommitSignal.COMPLETE: ("ok", "green"),
            PrecommitSignal.INCOMPLETE: ("warn", "yellow"),
            PrecommitSignal.NON_CANONICAL: ("warn", "yellow"),
            PrecommitSignal.NO_HOOKS: ("warn", "yellow"),
            PrecommitSignal.NO_FILE: ("info", "dim"),
        },
    )
    pc_detail = {
        PrecommitSignal.COMPLETE: "all hooks present",
        PrecommitSignal.INCOMPLETE: "missing canonical hooks",
        PrecommitSignal.NON_CANONICAL: "non-canonical entry pattern",
        PrecommitSignal.NO_HOOKS: "no vaultspec hooks found",
        PrecommitSignal.NO_FILE: "no .pre-commit-config.yaml",
    }.get(diag.precommit, str(diag.precommit))
    rows.append(
        {
            "component": "precommit",
            "status": Cell(pc_status, style=pc_style),
            "detail": pc_detail,
        }
    )

    # Rename integrity row
    ri_status, ri_style = _signal_status(
        diag.rename_integrity,
        {
            RenameIntegritySignal.CLEAN: ("ok", "green"),
            RenameIntegritySignal.MISMATCH: ("warn", "yellow"),
            RenameIntegritySignal.ERROR: ("error", "red"),
        },
    )
    ri_details = {
        RenameIntegritySignal.CLEAN: (
            "all rules, skills, and agents names are consistent"
        ),
        RenameIntegritySignal.MISMATCH: (
            f"{diag.rename_mismatch_count} name/filename mismatch(es) found; "
            "run vaultspec-core vault check rename-integrity"
        ),
        RenameIntegritySignal.ERROR: "failed to evaluate name/filename integrity",
    }
    ri_detail = ri_details.get(diag.rename_integrity, str(diag.rename_integrity))
    rows.append(
        {
            "component": "rename integrity",
            "status": Cell(ri_status, style=ri_style),
            "detail": ri_detail,
        }
    )

    # Install-mode coherence rows: the persisted declaration versus the shape of
    # the provisioned hook and MCP artifacts, one row per declared package. Each
    # labels the honest declared mode (dev stays dev even though it renders like
    # dependency) and flags whether that package's artifacts match. A floor row
    # follows a package only when its running version is below its declared
    # minimum. A workspace with no packages map (legacy, pre-install-mode) falls
    # back to a single informational row from core's own view.
    mode_map = {
        ModeMismatchSignal.CLEAN: ("ok", "green"),
        ModeMismatchSignal.MISMATCH: ("warn", "yellow"),
        ModeMismatchSignal.UNKNOWN: ("info", "dim"),
    }
    if diag.packages:
        for pkg_name, pkg_diag in sorted(diag.packages.items()):
            pm_status, pm_style = _signal_status(pkg_diag.mode_mismatch, mode_map)
            declared = pkg_diag.declared_mode.value
            if pkg_diag.mode_mismatch == ModeMismatchSignal.MISMATCH:
                pm_detail = (
                    f"declared {declared}; hook entries or MCP command do not "
                    "match; run vaultspec-core install --upgrade, or install "
                    "--mode to re-provision"
                )
            else:
                pm_detail = f"declared {declared}; artifacts match"
            rows.append(
                {
                    "component": f"install mode ({pkg_name})",
                    "status": Cell(pm_status, style=pm_style),
                    "detail": pm_detail,
                }
            )
            if pkg_diag.version_floor == VersionFloorSignal.BELOW:
                rows.append(
                    {
                        "component": f"version floor ({pkg_name})",
                        "status": Cell("error", style="red"),
                        "detail": (
                            f"running {pkg_diag.version_floor_running} is below "
                            f"the declared floor {pkg_diag.version_floor_minimum}; "
                            f"upgrade with uv tool upgrade {pkg_name}"
                        ),
                    }
                )
    else:
        mm_status, mm_style = _signal_status(diag.mode_mismatch, mode_map)
        mm_detail = {
            ModeMismatchSignal.CLEAN: "artifacts match the declared install mode",
            ModeMismatchSignal.MISMATCH: (
                "hook entries or MCP command do not match the declared mode; "
                "run vaultspec-core install --upgrade, or install --mode to "
                "re-provision"
            ),
            ModeMismatchSignal.UNKNOWN: "no install mode declared (legacy workspace)",
        }.get(diag.mode_mismatch, str(diag.mode_mismatch))
        rows.append(
            {
                "component": "install mode",
                "status": Cell(mm_status, style=mm_style),
                "detail": mm_detail,
            }
        )
        if diag.version_floor == VersionFloorSignal.BELOW:
            rows.append(
                {
                    "component": "version floor",
                    "status": Cell("error", style="red"),
                    "detail": (
                        f"running {diag.version_floor_running} is below the declared "
                        f"floor {diag.version_floor_minimum}; upgrade with "
                        f"uv tool upgrade vaultspec-core"
                    ),
                }
            )

    render_listing(
        rows,
        [Column("component"), Column("status"), Column("detail")],
        title="workspace diagnosis",
        empty="no components",
    )


def _signal_status(
    signal: object,
    mapping: dict,
) -> tuple[str, str]:
    """Map a signal value to a (status_label, style) pair."""
    val = signal.value if hasattr(signal, "value") else signal
    return mapping.get(signal, (f"unknown ({val})", "dim"))


def _provider_status(
    prov: "ProviderDiagnosis",
) -> tuple[str, str]:
    """Derive aggregate status for a provider diagnosis."""
    from vaultspec_core.core.diagnosis import (
        ContentSignal,
        ManifestEntrySignal,
        ProviderDirSignal,
    )

    if prov.manifest_entry == ManifestEntrySignal.NOT_INSTALLED:
        return ("skip", "dim")

    error_signals = (
        prov.manifest_entry == ManifestEntrySignal.ORPHANED,
        prov.dir_state == ProviderDirSignal.MISSING,
    )
    if any(error_signals):
        return ("error", "red")

    warn_signals = (
        prov.dir_state in (ProviderDirSignal.PARTIAL, ProviderDirSignal.MIXED),
        prov.manifest_entry == ManifestEntrySignal.UNTRACKED,
        any(s != ContentSignal.CLEAN for s in prov.content.values()),
    )
    if any(warn_signals):
        return ("warn", "yellow")

    return ("ok", "green")


def _doctor_exit_code(
    diag: "WorkspaceDiagnosis",
) -> int:
    """Compute the doctor exit code from a diagnosis.

    Returns:
        ``0`` if all ok/info, ``1`` if any warnings, ``2`` if any errors.
    """
    from vaultspec_core.core.diagnosis import (
        BuiltinVersionSignal,
        ConfigSignal,
        ContentSignal,
        FrameworkSignal,
        GitattributesSignal,
        GitignoreSignal,
        ManifestEntrySignal,
        ModeMismatchSignal,
        PrecommitSignal,
        ProviderDirSignal,
        RenameIntegritySignal,
        VaultContentSignal,
        VersionFloorSignal,
    )

    has_error = False
    has_warn = False

    if diag.framework in (
        FrameworkSignal.MISSING,
        FrameworkSignal.CORRUPTED,
    ):
        has_error = True
    if diag.gitignore == GitignoreSignal.CORRUPTED:
        has_error = True
    if diag.gitattributes == GitattributesSignal.CORRUPTED:
        has_error = True
    if diag.precommit in (
        PrecommitSignal.INCOMPLETE,
        PrecommitSignal.NON_CANONICAL,
        PrecommitSignal.NO_HOOKS,
    ):
        has_warn = True
    if diag.builtin_version == BuiltinVersionSignal.DELETED:
        has_error = True
    elif diag.builtin_version == BuiltinVersionSignal.MODIFIED:
        has_warn = True

    if diag.migration_status == "pending":
        has_warn = True
    if diag.vault_content in (
        VaultContentSignal.ANNOTATIONS,
        VaultContentSignal.UNREADABLE,
    ):
        has_warn = True

    if diag.rename_integrity == RenameIntegritySignal.ERROR:
        has_error = True
    elif diag.rename_integrity == RenameIntegritySignal.MISMATCH:
        has_warn = True

    # A declared-vs-observed install-mode mismatch is a warning; a running
    # version below the committed floor is a hard error on doctor, mirroring the
    # refuse-and-tell that install and sync raise. Weighed per declared package
    # when a packages map exists so a companion package's mismatch or floor
    # violation counts; UNKNOWN and CLEAN are neither. A legacy workspace with no
    # packages map falls back to core's own top-level view.
    if diag.packages:
        for pkg_diag in diag.packages.values():
            if pkg_diag.mode_mismatch == ModeMismatchSignal.MISMATCH:
                has_warn = True
            if pkg_diag.version_floor == VersionFloorSignal.BELOW:
                has_error = True
    else:
        if diag.mode_mismatch == ModeMismatchSignal.MISMATCH:
            has_warn = True
        if diag.version_floor == VersionFloorSignal.BELOW:
            has_error = True

    for prov in diag.providers.values():
        if prov.manifest_entry == ManifestEntrySignal.NOT_INSTALLED:
            continue
        if prov.manifest_entry == ManifestEntrySignal.ORPHANED:
            has_error = True
        elif prov.manifest_entry == ManifestEntrySignal.UNTRACKED:
            has_warn = True
        if prov.dir_state == ProviderDirSignal.MISSING:
            has_error = True
        elif prov.dir_state in (
            ProviderDirSignal.EMPTY,
            ProviderDirSignal.PARTIAL,
        ):
            has_warn = True
        # ProviderDirSignal.MIXED is a soft, informational signal: it means the
        # provider directory carries extra files vaultspec does not own. That is
        # benign (genuine managed-content drift surfaces via ContentSignal), so
        # it must not fail the doctor exit code and block markdown commits via
        # the bundled spec-check hook (issue #122).
        if prov.config in (
            ConfigSignal.MISSING,
            ConfigSignal.FOREIGN,
            ConfigSignal.REGISTRY_DRIFT,
        ):
            has_warn = True
        if any(
            s
            in (
                ContentSignal.STALE,
                ContentSignal.DIVERGED,
                ContentSignal.MISSING,
            )
            for s in prov.content.values()
        ):
            has_warn = True

    if has_error:
        return 2
    if has_warn:
        return 1
    return 0


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
