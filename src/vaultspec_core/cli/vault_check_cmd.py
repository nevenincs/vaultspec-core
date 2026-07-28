"""Vault health-check, sanitize, and repair verbs.

Registers the ``vaultspec-core vault check ...`` subcommands (mounted on
:data:`vaultspec_core.cli.vault_cmd.check_app`), the deprecated
``vaultspec-core vault sanitize annotations`` verb (mounted on
:data:`vaultspec_core.cli.vault_cmd.sanitize_app`), and the top-level
``vaultspec-core vault repair`` verb (mounted on
:data:`vaultspec_core.cli.vault_cmd.vault_app`). Split out of
:mod:`vaultspec_core.cli.vault_cmd` to keep that module under the project's
line-count ceiling; all commands re-export through ``vault_cmd`` so no
import site outside the package changes. All backend logic lives in
:mod:`vaultspec_core.vaultcore.checks` and :mod:`vaultspec_core.vaultcore.repair`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

import typer

from vaultspec_core.cli._target import TargetOption, apply_target

if TYPE_CHECKING:
    import typer as _typer

    from vaultspec_core.vaultcore.checks._base import CheckResult

__all__ = [
    "register_check_commands",
    "register_repair_command",
    "register_sanitize_commands",
]


# ---- vault check subcommands ------------------------------------------------


def _reject_fix(check_name: str, fix: bool) -> None:
    """Error and exit if --fix is used on a check that doesn't support it."""
    if fix:
        from vaultspec_core.console import get_console

        console = get_console()
        console.print(
            f"[red]Error: 'vaultspec-core vault check {check_name}'"
            " has no auto-fix capabilities.[/red]"
        )
        raise typer.Exit(code=1)


def _check_status(results: list[CheckResult]) -> str:
    """Aggregate canonical outcome word for a set of check results.

    ``failed`` when any error is present, ``updated`` when ``--fix``
    corrected something, else ``unchanged``.
    """
    if any(r.error_count for r in results):
        return "failed"
    if any(r.fixed_count for r in results):
        return "updated"
    return "unchanged"


def _render_and_exit(
    result: CheckResult,
    verbose: bool,
    json_output: bool = False,
    *,
    command: str,
) -> None:
    """Render a CheckResult and exit with appropriate code."""
    if json_output:
        import dataclasses
        import json

        from vaultspec_core.cli.rendering import json_envelope

        envelope = json_envelope(
            command, _check_status([result]), dataclasses.asdict(result)
        )
        typer.echo(json.dumps(envelope, indent=2, default=str))
        raise typer.Exit(code=1 if result.error_count else 0)
    from vaultspec_core.console import get_console
    from vaultspec_core.vaultcore.checks import render_check_result

    console = get_console()
    render_check_result(console, result, verbose=verbose)
    if result.error_count:
        raise typer.Exit(code=1)


# ---- vault repair -----------------------------------------------------------


def register_repair_command(vault_app: _typer.Typer) -> None:
    """Register the ``repair`` verb on *vault_app*.

    Args:
        vault_app: The ``vault`` command group to mount the verb on.
    """

    @vault_app.command("repair")
    def cmd_repair(  # pyright: ignore[reportUnusedFunction]
        dry_run: Annotated[
            bool,
            typer.Option("--dry-run", help="Preview repair actions without writing"),
        ] = False,
        include_index: Annotated[
            bool,
            typer.Option(
                "--include-index/--no-index",
                help="Refresh generated feature indexes during repair",
            ),
        ] = True,
        feature: Annotated[
            str | None,
            typer.Option("--feature", "-f", help="Scope repair to one feature tag"),
        ] = None,
        verbose: Annotated[
            bool, typer.Option("--verbose", "-v", help="Show INFO-level diagnostics")
        ] = False,
        json_output: Annotated[
            bool, typer.Option("--json", help="Output as JSON")
        ] = False,
        target: TargetOption = None,
    ) -> None:
        """Run the operator repair pipeline for vault content.

        The repair pipeline is broader than ``vaultspec-core vault check all --fix``: it
        reports preflight and migration state, runs checks, applies safe
        check-level fixes unless ``--dry-run`` is set, refreshes generated
        feature indexes unless ``--no-index`` is set, rebuilds graph state,
        and runs a postcheck pass.
        """
        apply_target(target)
        from vaultspec_core.core.types import get_context as _get_ctx
        from vaultspec_core.vaultcore.repair import run_repair_pipeline

        run = run_repair_pipeline(
            _get_ctx().target_dir,
            dry_run=dry_run,
            include_index=include_index,
            feature=feature,
        )
        if not dry_run and run.changed_files:
            from vaultspec_core.cli._cache_hook import invalidate_graph_cache

            invalidate_graph_cache(_get_ctx().target_dir)
        if json_output:
            import json

            from vaultspec_core.cli._repair_render import repair_payload
            from vaultspec_core.cli.rendering import json_envelope

            if run.error_count:
                repair_status = "failed"
            elif run.fixed_count:
                repair_status = "updated"
            else:
                repair_status = "unchanged"
            typer.echo(
                json.dumps(
                    json_envelope("vault.repair", repair_status, repair_payload(run)),
                    indent=2,
                    default=str,
                )
            )
            raise typer.Exit(code=1 if run.error_count else 0)

        from vaultspec_core.cli._repair_render import render_repair_run

        render_repair_run(run, verbose=verbose)
        if run.error_count:
            raise typer.Exit(code=1)


def register_check_commands(check_app: _typer.Typer) -> None:
    """Register the ``vault check ...`` verbs on *check_app*.

    Args:
        check_app: The ``vault check`` command group to mount the verbs on.
    """
    _register_check_commands_content(check_app)
    _register_check_commands_hygiene(check_app)
    _register_check_commands_graph(check_app)
    _register_check_commands_structural(check_app)


def _register_check_commands_content(check_app: _typer.Typer) -> None:
    """Register a subset of the ``vault check ...`` verbs on *check_app*.

    Args:
        check_app: The ``vault check`` command group to mount the verbs on.
    """

    @check_app.command("all")
    def cmd_check_all(  # pyright: ignore[reportUnusedFunction]
        fix: Annotated[
            bool,
            typer.Option("--fix", help="Apply safe auto-corrections to vault content"),
        ] = False,
        feature: Annotated[
            str | None, typer.Option("--feature", "-f", help="Filter by feature tag")
        ] = None,
        verbose: Annotated[
            bool, typer.Option("--verbose", "-v", help="Show INFO-level diagnostics")
        ] = False,
        json_output: Annotated[
            bool, typer.Option("--json", help="Output as JSON")
        ] = False,
        no_hints: Annotated[
            bool, typer.Option("--no-hints", help="Suppress next-step advisory hints")
        ] = False,
        target: TargetOption = None,
    ) -> None:
        """Run all vault health checks."""
        apply_target(target)
        from vaultspec_core.console import get_console
        from vaultspec_core.core.types import get_context as _get_ctx
        from vaultspec_core.vaultcore.checks import render_check_result, run_all_checks

        console = get_console()
        results = run_all_checks(_get_ctx().target_dir, feature=feature, fix=fix)

        if fix and sum(r.fixed_count for r in results) > 0:
            from vaultspec_core.cli._cache_hook import invalidate_graph_cache

            invalidate_graph_cache(_get_ctx().target_dir)

        total_errors = sum(r.error_count for r in results)
        outcome = "failed" if total_errors > 0 else "unchanged"

        from vaultspec_core.cli.rendering import emit_next_step_hint

        hint_dict = emit_next_step_hint(
            command="vault.check.all",
            outcome=outcome,
            json_output=json_output,
            no_hints=no_hints,
        )

        if json_output:
            import dataclasses
            import json

            from vaultspec_core.cli.rendering import json_envelope

            envelope = json_envelope(
                "vault.check.all",
                _check_status(results),
                {"checks": [dataclasses.asdict(r) for r in results]},
                hints=hint_dict,
            )
            typer.echo(json.dumps(envelope, indent=2, default=str))
            raise typer.Exit(0 if total_errors == 0 else 1)

        console.print("[bold]Vault Check  - All[/bold]")
        for r in results:
            render_check_result(console, r, verbose=verbose)

        total_warnings = sum(r.warning_count for r in results)
        total_fixed = sum(r.fixed_count for r in results)

        console.print()
        parts: list[str] = []
        if total_errors:
            parts.append(
                f"[red]{total_errors} error{'s' if total_errors != 1 else ''}[/red]"
            )
        if total_warnings:
            sfx = "s" if total_warnings != 1 else ""
            parts.append(f"[yellow]{total_warnings} warning{sfx}[/yellow]")
        if total_fixed:
            parts.append(f"[green]{total_fixed} fixed[/green]")
        if parts:
            console.print(f"  Total: {', '.join(parts)}")
        else:
            console.print("  [green]All checks passed.[/green]")

        if total_errors:
            raise typer.Exit(code=1)

    @check_app.command("body-links")
    def cmd_check_body_links(  # pyright: ignore[reportUnusedFunction]
        feature: Annotated[
            str | None, typer.Option("--feature", "-f", help="Filter by feature tag")
        ] = None,
        verbose: Annotated[
            bool, typer.Option("--verbose", "-v", help="Show INFO-level diagnostics")
        ] = False,
        json_output: Annotated[
            bool, typer.Option("--json", help="Output as JSON")
        ] = False,
        target: TargetOption = None,
    ) -> None:
        """Find wiki-links and markdown path links in document body text."""
        apply_target(target)
        from vaultspec_core.core.types import get_context as _get_ctx
        from vaultspec_core.graph import VaultGraph
        from vaultspec_core.vaultcore.checks import check_body_links

        graph = VaultGraph(_get_ctx().target_dir)
        snapshot = graph.to_snapshot()
        result = check_body_links(
            _get_ctx().target_dir, snapshot=snapshot, feature=feature
        )
        _render_and_exit(
            result, verbose, json_output=json_output, command="vault.check.body-links"
        )

    @check_app.command("exec-mapping")
    def cmd_check_exec_mapping(  # pyright: ignore[reportUnusedFunction]
        feature: Annotated[
            str | None, typer.Option("--feature", "-f", help="Filter by feature tag")
        ] = None,
        verbose: Annotated[
            bool, typer.Option("--verbose", "-v", help="Show INFO-level diagnostics")
        ] = False,
        json_output: Annotated[
            bool, typer.Option("--json", help="Output as JSON")
        ] = False,
        target: TargetOption = None,
    ) -> None:
        """Check execution records map to a live Step in their parent plan."""
        apply_target(target)
        from vaultspec_core.core.types import get_context as _get_ctx
        from vaultspec_core.graph import VaultGraph
        from vaultspec_core.vaultcore.checks import check_exec_mapping

        snapshot = VaultGraph(_get_ctx().target_dir).to_snapshot()
        result = check_exec_mapping(
            _get_ctx().target_dir, snapshot=snapshot, feature=feature
        )
        _render_and_exit(
            result, verbose, json_output=json_output, command="vault.check.exec-mapping"
        )

    @check_app.command("body-sections")
    def cmd_check_body_sections(  # pyright: ignore[reportUnusedFunction]
        feature: Annotated[
            str | None, typer.Option("--feature", "-f", help="Filter by feature tag")
        ] = None,
        verbose: Annotated[
            bool, typer.Option("--verbose", "-v", help="Show INFO-level diagnostics")
        ] = False,
        json_output: Annotated[
            bool, typer.Option("--json", help="Output as JSON")
        ] = False,
        target: TargetOption = None,
    ) -> None:
        """Check document bodies carry the sections their template mandates."""
        apply_target(target)
        from vaultspec_core.core.types import get_context as _get_ctx
        from vaultspec_core.graph import VaultGraph
        from vaultspec_core.vaultcore.checks import check_body_sections

        snapshot = VaultGraph(_get_ctx().target_dir).to_snapshot()
        result = check_body_sections(
            _get_ctx().target_dir, snapshot=snapshot, feature=feature
        )
        _render_and_exit(
            result,
            verbose,
            json_output=json_output,
            command="vault.check.body-sections",
        )

    @check_app.command("annotations")
    def cmd_check_annotations(  # pyright: ignore[reportUnusedFunction]
        fix: Annotated[
            bool,
            typer.Option("--fix", help="Strip generated template annotations"),
        ] = False,
        feature: Annotated[
            str | None, typer.Option("--feature", "-f", help="Filter by feature tag")
        ] = None,
        verbose: Annotated[
            bool, typer.Option("--verbose", "-v", help="Show INFO-level diagnostics")
        ] = False,
        json_output: Annotated[
            bool, typer.Option("--json", help="Output as JSON")
        ] = False,
        target: TargetOption = None,
    ) -> None:
        """Find generated template annotations in vault documents."""
        apply_target(target)
        from vaultspec_core.core.types import get_context as _get_ctx
        from vaultspec_core.vaultcore.checks import check_annotations

        result = check_annotations(_get_ctx().target_dir, feature=feature, fix=fix)
        _render_and_exit(
            result, verbose, json_output=json_output, command="vault.check.annotations"
        )


def _register_check_commands_hygiene(check_app: _typer.Typer) -> None:
    """Register a subset of the ``vault check ...`` verbs on *check_app*.

    Args:
        check_app: The ``vault check`` command group to mount the verbs on.
    """

    @check_app.command("markdown")
    def cmd_check_markdown(  # pyright: ignore[reportUnusedFunction]
        fix: Annotated[
            bool,
            typer.Option("--fix", help="Repair markdown hygiene issues"),
        ] = False,
        feature: Annotated[
            str | None, typer.Option("--feature", "-f", help="Filter by feature tag")
        ] = None,
        verbose: Annotated[
            bool, typer.Option("--verbose", "-v", help="Show INFO-level diagnostics")
        ] = False,
        json_output: Annotated[
            bool, typer.Option("--json", help="Output as JSON")
        ] = False,
        target: TargetOption = None,
    ) -> None:
        """Check and optionally fix markdown hygiene (whitespace, blank runs, \
newline)."""
        apply_target(target)
        from vaultspec_core.core.types import get_context as _get_ctx
        from vaultspec_core.vaultcore.checks import check_markdown

        result = check_markdown(_get_ctx().target_dir, feature=feature, fix=fix)
        _render_and_exit(
            result, verbose, json_output=json_output, command="vault.check.markdown"
        )

    @check_app.command("placeholders")
    def cmd_check_placeholders(  # pyright: ignore[reportUnusedFunction]
        feature: Annotated[
            str | None, typer.Option("--feature", "-f", help="Filter by feature tag")
        ] = None,
        verbose: Annotated[
            bool, typer.Option("--verbose", "-v", help="Show INFO-level diagnostics")
        ] = False,
        json_output: Annotated[
            bool, typer.Option("--json", help="Output as JSON")
        ] = False,
        target: TargetOption = None,
    ) -> None:
        """Find unreplaced {...} template placeholders in document body prose."""
        apply_target(target)
        from vaultspec_core.core.types import get_context as _get_ctx
        from vaultspec_core.graph import VaultGraph
        from vaultspec_core.vaultcore.checks import check_placeholders

        graph = VaultGraph(_get_ctx().target_dir)
        snapshot = graph.to_snapshot()
        result = check_placeholders(
            _get_ctx().target_dir, snapshot=snapshot, feature=feature
        )
        _render_and_exit(
            result,
            verbose,
            json_output=json_output,
            command="vault.check.placeholders",
        )

    @check_app.command("dangling")
    def cmd_check_dangling(  # pyright: ignore[reportUnusedFunction]
        fix: Annotated[
            bool,
            typer.Option("--fix", help="Apply safe auto-corrections to vault content"),
        ] = False,
        feature: Annotated[
            str | None, typer.Option("--feature", "-f", help="Filter by feature tag")
        ] = None,
        verbose: Annotated[
            bool, typer.Option("--verbose", "-v", help="Show INFO-level diagnostics")
        ] = False,
        json_output: Annotated[
            bool, typer.Option("--json", help="Output as JSON")
        ] = False,
        target: TargetOption = None,
    ) -> None:
        """Find wiki-links in related: frontmatter that resolve to no document."""
        apply_target(target)
        from vaultspec_core.core.types import get_context as _get_ctx
        from vaultspec_core.graph import VaultGraph
        from vaultspec_core.vaultcore.checks import check_dangling

        graph = VaultGraph(_get_ctx().target_dir)
        result = check_dangling(
            _get_ctx().target_dir, graph=graph, feature=feature, fix=fix
        )
        _render_and_exit(
            result, verbose, json_output=json_output, command="vault.check.dangling"
        )

    @check_app.command("orphans")
    def cmd_check_orphans(  # pyright: ignore[reportUnusedFunction]
        fix: Annotated[
            bool,
            typer.Option("--fix", help="Apply safe auto-corrections to vault content"),
        ] = False,
        feature: Annotated[
            str | None, typer.Option("--feature", "-f", help="Filter by feature tag")
        ] = None,
        verbose: Annotated[
            bool, typer.Option("--verbose", "-v", help="Show INFO-level diagnostics")
        ] = False,
        json_output: Annotated[
            bool, typer.Option("--json", help="Output as JSON")
        ] = False,
        target: TargetOption = None,
    ) -> None:
        """Find documents with no incoming wiki-links."""
        apply_target(target)
        _reject_fix("orphans", fix)
        from vaultspec_core.core.types import get_context as _get_ctx
        from vaultspec_core.graph import VaultGraph
        from vaultspec_core.vaultcore.checks import check_orphans

        graph = VaultGraph(_get_ctx().target_dir)
        result = check_orphans(_get_ctx().target_dir, graph=graph, feature=feature)
        _render_and_exit(
            result, verbose, json_output=json_output, command="vault.check.orphans"
        )

    @check_app.command("frontmatter")
    def cmd_check_frontmatter(  # pyright: ignore[reportUnusedFunction]
        fix: Annotated[
            bool,
            typer.Option("--fix", help="Apply safe auto-corrections to vault content"),
        ] = False,
        feature: Annotated[
            str | None, typer.Option("--feature", "-f", help="Filter by feature tag")
        ] = None,
        verbose: Annotated[
            bool, typer.Option("--verbose", "-v", help="Show INFO-level diagnostics")
        ] = False,
        json_output: Annotated[
            bool, typer.Option("--json", help="Output as JSON")
        ] = False,
        target: TargetOption = None,
    ) -> None:
        """Validate document frontmatter against vault schema."""
        apply_target(target)
        from vaultspec_core.core.types import get_context as _get_ctx
        from vaultspec_core.graph import VaultGraph
        from vaultspec_core.vaultcore.checks import check_frontmatter

        graph = VaultGraph(_get_ctx().target_dir)
        snapshot = graph.to_snapshot()
        result = check_frontmatter(
            _get_ctx().target_dir, snapshot=snapshot, feature=feature, fix=fix
        )
        _render_and_exit(
            result, verbose, json_output=json_output, command="vault.check.frontmatter"
        )


def _register_check_commands_graph(check_app: _typer.Typer) -> None:
    """Register a subset of the ``vault check ...`` verbs on *check_app*.

    Args:
        check_app: The ``vault check`` command group to mount the verbs on.
    """

    @check_app.command("modified-stamp")
    def cmd_check_modified_stamp(  # pyright: ignore[reportUnusedFunction]
        fix: Annotated[
            bool,
            typer.Option("--fix", help="Apply safe auto-corrections to vault content"),
        ] = False,
        feature: Annotated[
            str | None, typer.Option("--feature", "-f", help="Filter by feature tag")
        ] = None,
        verbose: Annotated[
            bool, typer.Option("--verbose", "-v", help="Show INFO-level diagnostics")
        ] = False,
        json_output: Annotated[
            bool, typer.Option("--json", help="Output as JSON")
        ] = False,
        target: TargetOption = None,
    ) -> None:
        """Validate and reconcile the modified recency stamp on every document."""
        apply_target(target)
        from vaultspec_core.core.types import get_context as _get_ctx
        from vaultspec_core.graph import VaultGraph
        from vaultspec_core.vaultcore.checks import check_modified_stamp

        graph = VaultGraph(_get_ctx().target_dir)
        snapshot = graph.to_snapshot()
        result = check_modified_stamp(
            _get_ctx().target_dir, snapshot=snapshot, feature=feature, fix=fix
        )
        _render_and_exit(
            result,
            verbose,
            json_output=json_output,
            command="vault.check.modified-stamp",
        )

    @check_app.command("links")
    def cmd_check_links(  # pyright: ignore[reportUnusedFunction]
        fix: Annotated[
            bool,
            typer.Option("--fix", help="Apply safe auto-corrections to vault content"),
        ] = False,
        feature: Annotated[
            str | None, typer.Option("--feature", "-f", help="Filter by feature tag")
        ] = None,
        verbose: Annotated[
            bool, typer.Option("--verbose", "-v", help="Show INFO-level diagnostics")
        ] = False,
        json_output: Annotated[
            bool, typer.Option("--json", help="Output as JSON")
        ] = False,
        target: TargetOption = None,
    ) -> None:
        """Check wiki-links follow Obsidian convention (no .md extension)."""
        apply_target(target)
        from vaultspec_core.core.types import get_context as _get_ctx
        from vaultspec_core.graph import VaultGraph
        from vaultspec_core.vaultcore.checks import check_links

        graph = VaultGraph(_get_ctx().target_dir)
        snapshot = graph.to_snapshot()
        result = check_links(
            _get_ctx().target_dir, snapshot=snapshot, feature=feature, fix=fix
        )
        _render_and_exit(
            result, verbose, json_output=json_output, command="vault.check.links"
        )

    @check_app.command("features")
    def cmd_check_features(  # pyright: ignore[reportUnusedFunction]
        fix: Annotated[
            bool,
            typer.Option("--fix", help="Apply safe auto-corrections to vault content"),
        ] = False,
        feature: Annotated[
            str | None, typer.Option("--feature", "-f", help="Filter by feature tag")
        ] = None,
        verbose: Annotated[
            bool, typer.Option("--verbose", "-v", help="Show INFO-level diagnostics")
        ] = False,
        json_output: Annotated[
            bool, typer.Option("--json", help="Output as JSON")
        ] = False,
        target: TargetOption = None,
    ) -> None:
        """Check feature tag completeness  - missing doc types."""
        apply_target(target)
        _reject_fix("features", fix)
        from vaultspec_core.core.types import get_context as _get_ctx
        from vaultspec_core.graph import VaultGraph
        from vaultspec_core.vaultcore.checks import check_features

        graph = VaultGraph(_get_ctx().target_dir)
        snapshot = graph.to_snapshot()
        result = check_features(
            _get_ctx().target_dir, snapshot=snapshot, feature=feature
        )
        _render_and_exit(
            result, verbose, json_output=json_output, command="vault.check.features"
        )

    @check_app.command("references")
    def cmd_check_references(  # pyright: ignore[reportUnusedFunction]
        fix: Annotated[
            bool,
            typer.Option("--fix", help="Apply safe auto-corrections to vault content"),
        ] = False,
        feature: Annotated[
            str | None, typer.Option("--feature", "-f", help="Filter by feature tag")
        ] = None,
        verbose: Annotated[
            bool, typer.Option("--verbose", "-v", help="Show INFO-level diagnostics")
        ] = False,
        json_output: Annotated[
            bool, typer.Option("--json", help="Output as JSON")
        ] = False,
        target: TargetOption = None,
    ) -> None:
        """Check for missing cross-references within features."""
        apply_target(target)
        from vaultspec_core.core.types import get_context as _get_ctx
        from vaultspec_core.graph import VaultGraph
        from vaultspec_core.vaultcore.checks import check_references

        graph = VaultGraph(_get_ctx().target_dir)
        result = check_references(
            _get_ctx().target_dir, graph=graph, feature=feature, fix=fix
        )
        _render_and_exit(
            result, verbose, json_output=json_output, command="vault.check.references"
        )

    @check_app.command("schema")
    def cmd_check_schema(  # pyright: ignore[reportUnusedFunction]
        fix: Annotated[
            bool,
            typer.Option("--fix", help="Apply safe auto-corrections to vault content"),
        ] = False,
        feature: Annotated[
            str | None, typer.Option("--feature", "-f", help="Filter by feature tag")
        ] = None,
        verbose: Annotated[
            bool, typer.Option("--verbose", "-v", help="Show INFO-level diagnostics")
        ] = False,
        json_output: Annotated[
            bool, typer.Option("--json", help="Output as JSON")
        ] = False,
        target: TargetOption = None,
    ) -> None:
        """Enforce schema rules: ADRs must ref research, plans must ref ADRs."""
        apply_target(target)
        from vaultspec_core.core.types import get_context as _get_ctx
        from vaultspec_core.graph import VaultGraph
        from vaultspec_core.vaultcore.checks import check_schema

        graph = VaultGraph(_get_ctx().target_dir)
        result = check_schema(
            _get_ctx().target_dir, graph=graph, feature=feature, fix=fix
        )
        _render_and_exit(
            result, verbose, json_output=json_output, command="vault.check.schema"
        )


def _register_check_commands_structural(check_app: _typer.Typer) -> None:
    """Register a subset of the ``vault check ...`` verbs on *check_app*.

    Args:
        check_app: The ``vault check`` command group to mount the verbs on.
    """

    @check_app.command("adr-status")
    def cmd_check_adr_status(  # pyright: ignore[reportUnusedFunction]
        fix: Annotated[
            bool,
            typer.Option("--fix", help="Apply safe auto-corrections to vault content"),
        ] = False,
        feature: Annotated[
            str | None, typer.Option("--feature", "-f", help="Filter by feature tag")
        ] = None,
        verbose: Annotated[
            bool, typer.Option("--verbose", "-v", help="Show INFO-level diagnostics")
        ] = False,
        json_output: Annotated[
            bool, typer.Option("--json", help="Output as JSON")
        ] = False,
        target: TargetOption = None,
    ) -> None:
        """Validate ADR status against the canonical taxonomy."""
        apply_target(target)
        from vaultspec_core.core.types import get_context as _get_ctx
        from vaultspec_core.graph import VaultGraph
        from vaultspec_core.vaultcore.checks import check_adr_status

        graph = VaultGraph(_get_ctx().target_dir)
        snapshot = graph.to_snapshot()
        result = check_adr_status(
            _get_ctx().target_dir, snapshot=snapshot, feature=feature, fix=fix
        )
        _render_and_exit(
            result, verbose, json_output=json_output, command="vault.check.adr-status"
        )

    @check_app.command("code-boundary")
    def cmd_check_code_boundary(  # pyright: ignore[reportUnusedFunction]
        feature: Annotated[
            str | None,
            typer.Option(
                "--feature",
                "-f",
                help="Restrict the scanned record stems to one feature's documents",
            ),
        ] = None,
        verbose: Annotated[
            bool, typer.Option("--verbose", "-v", help="Show INFO-level diagnostics")
        ] = False,
        json_output: Annotated[
            bool, typer.Option("--json", help="Output as JSON")
        ] = False,
        target: TargetOption = None,
    ) -> None:
        """Scan source files for references to the project's own vault records.

        Opt-in and advisory: findings are warnings, the exit code stays zero,
        and nothing is mutated. Not part of `vaultspec-core vault check all`.
        """
        apply_target(target)
        from vaultspec_core.core.types import get_context as _get_ctx
        from vaultspec_core.vaultcore.checks import check_code_boundary

        result = check_code_boundary(_get_ctx().target_dir, feature=feature)
        _render_and_exit(
            result,
            verbose,
            json_output=json_output,
            command="vault.check.code-boundary",
        )

    @check_app.command("structure")
    def cmd_check_structure(  # pyright: ignore[reportUnusedFunction]
        fix: Annotated[
            bool,
            typer.Option("--fix", help="Apply safe auto-corrections to vault content"),
        ] = False,
        verbose: Annotated[
            bool, typer.Option("--verbose", "-v", help="Show INFO-level diagnostics")
        ] = False,
        json_output: Annotated[
            bool, typer.Option("--json", help="Output as JSON")
        ] = False,
        target: TargetOption = None,
    ) -> None:
        """Check vault directory structure and filename conventions."""
        apply_target(target)
        from vaultspec_core.core.types import get_context as _get_ctx
        from vaultspec_core.graph import VaultGraph
        from vaultspec_core.vaultcore.checks import check_structure

        graph = VaultGraph(_get_ctx().target_dir)
        snapshot = graph.to_snapshot()
        result = check_structure(_get_ctx().target_dir, snapshot=snapshot, fix=fix)
        _render_and_exit(
            result, verbose, json_output=json_output, command="vault.check.structure"
        )

    @check_app.command("rename-integrity")
    def cmd_check_rename_integrity(  # pyright: ignore[reportUnusedFunction]
        fix: Annotated[
            bool,
            typer.Option(
                "--fix", help="Filename-wins: update frontmatter name to match filename"
            ),
        ] = False,
        fix_frontmatter_wins: Annotated[
            bool,
            typer.Option(
                "--fix-frontmatter-wins",
                help=(
                    "Frontmatter-wins: physically rename file to match frontmatter name"
                ),
            ),
        ] = False,
        verbose: Annotated[
            bool, typer.Option("--verbose", "-v", help="Show INFO-level diagnostics")
        ] = False,
        json_output: Annotated[
            bool, typer.Option("--json", help="Output as JSON")
        ] = False,
        target: TargetOption = None,
    ) -> None:
        """Check name/filename integrity for rules, skills, and agents."""
        apply_target(target)
        from vaultspec_core.core.types import get_context as _get_ctx
        from vaultspec_core.vaultcore.checks import check_rename_integrity

        root_dir = _get_ctx().target_dir

        def confirm_fn(prompt: str) -> bool:
            return typer.confirm(prompt, default=True)

        result = check_rename_integrity(
            root_dir,
            fix=fix,
            fix_frontmatter_wins=fix_frontmatter_wins,
            confirm_fn=confirm_fn if not json_output else None,
        )
        _render_and_exit(
            result,
            verbose,
            json_output=json_output,
            command="vault.check.rename-integrity",
        )

    @check_app.command("encoding")
    def cmd_check_encoding(  # pyright: ignore[reportUnusedFunction]
        verbose: Annotated[
            bool, typer.Option("--verbose", "-v", help="Show INFO-level diagnostics")
        ] = False,
        json_output: Annotated[
            bool, typer.Option("--json", help="Output as JSON")
        ] = False,
        target: TargetOption = None,
    ) -> None:
        """Surface .vault/ documents that are not valid UTF-8 (detection only).

        Encoding is validated vault-wide and takes no ``--feature`` filter: a
        non-UTF-8 document has no parseable feature tag to scope by.
        """
        apply_target(target)
        from vaultspec_core.core.types import get_context as _get_ctx
        from vaultspec_core.vaultcore.checks import check_encoding

        result = check_encoding(_get_ctx().target_dir)
        _render_and_exit(
            result, verbose, json_output=json_output, command="vault.check.encoding"
        )

    @check_app.command("feature-rename-integrity")
    def cmd_check_feature_rename_integrity(  # pyright: ignore[reportUnusedFunction]
        verbose: Annotated[
            bool, typer.Option("--verbose", "-v", help="Show INFO-level diagnostics")
        ] = False,
        json_output: Annotated[
            bool, typer.Option("--json", help="Output as JSON")
        ] = False,
        target: TargetOption = None,
    ) -> None:
        """Surface exec folders whose feature disagrees with their records' tag.

        Detection only: it reports post-rename drift between an exec folder name
        and the ``#feature`` tag of the records inside it. It is vault-wide and
        takes no ``--feature`` filter; index/staleness defer to ``check_features``
        and filename/directory grammar to ``check_structure``.
        """
        apply_target(target)
        from vaultspec_core.core.types import get_context as _get_ctx
        from vaultspec_core.vaultcore.checks import check_feature_rename_integrity

        result = check_feature_rename_integrity(_get_ctx().target_dir)
        _render_and_exit(
            result,
            verbose,
            json_output=json_output,
            command="vault.check.feature-rename-integrity",
        )


def register_sanitize_commands(sanitize_app: _typer.Typer) -> None:
    """Register the deprecated ``sanitize`` verbs on *sanitize_app*.

    Args:
        sanitize_app: The ``vault sanitize`` command group to mount the verbs on.
    """

    @sanitize_app.command("annotations")
    def cmd_sanitize_annotations(  # pyright: ignore[reportUnusedFunction]
        feature: Annotated[
            str | None, typer.Option("--feature", "-f", help="Filter by feature tag")
        ] = None,
        dry_run: Annotated[
            bool, typer.Option("--dry-run", help="Preview annotation stripping")
        ] = False,
        verbose: Annotated[
            bool, typer.Option("--verbose", "-v", help="Show stripped files")
        ] = False,
        json_output: Annotated[
            bool, typer.Option("--json", help="Output as JSON")
        ] = False,
        target: TargetOption = None,
    ) -> None:
        """Strip generated template annotations from vault documents."""
        apply_target(target)
        from vaultspec_core.core.types import get_context as _get_ctx
        from vaultspec_core.vaultcore.checks import check_annotations

        if not json_output:
            from vaultspec_core.console import get_console

            console = get_console()
            console.print(
                "[yellow]Deprecation Warning: "
                "'vaultspec-core vault sanitize annotations' is deprecated. "
                "Please use 'vaultspec-core vault check annotations --fix' "
                "instead.[/yellow]"
            )

        result = check_annotations(
            _get_ctx().target_dir, feature=feature, fix=True, dry_run=dry_run
        )
        if not dry_run and result.fixed_count > 0:
            from vaultspec_core.cli._cache_hook import invalidate_graph_cache

            invalidate_graph_cache(_get_ctx().target_dir)
        _render_and_exit(
            result,
            verbose or dry_run,
            json_output=json_output,
            command="vault.sanitize.annotations",
        )
