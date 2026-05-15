"""Vault command group  - create, query, graph, check, and audit ``.vault/`` records.

Sub-groups: ``vaultspec-core vault feature`` (:data:`feature_app`),
``vaultspec-core vault graph`` (:data:`graph_app`), and
``vaultspec-core vault check`` (:data:`check_app`). Delegates to
:mod:`vaultspec_core.vaultcore.query`, :mod:`vaultspec_core.vaultcore.hydration`,
:mod:`vaultspec_core.vaultcore.checks`, and :mod:`vaultspec_core.graph` for
all backend logic. Mounted onto :data:`.root.app` as the ``vault`` command group.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

import typer

from vaultspec_core.cli._errors import handle_error as _handle_error
from vaultspec_core.cli._target import TargetOption, apply_target

if TYPE_CHECKING:
    from rich.console import Console

    from vaultspec_core.graph.api import VaultGraph
    from vaultspec_core.vaultcore.checks._base import CheckResult
    from vaultspec_core.vaultcore.repair import RepairRun


vault_app = typer.Typer(
    help="Create, query, and audit records in the .vault/ project history.",
    no_args_is_help=True,
)

feature_app = typer.Typer(
    help="Manage vault feature tags.",
    no_args_is_help=True,
)
vault_app.add_typer(feature_app, name="feature")

graph_app = typer.Typer(
    help="Visualise and export the vault document graph.",
    invoke_without_command=True,
)
vault_app.add_typer(graph_app, name="graph")

check_app = typer.Typer(
    help="Run vault health checks with optional auto-fix.",
    no_args_is_help=True,
)
vault_app.add_typer(check_app, name="check")

sanitize_app = typer.Typer(
    help="Run explicit vault sanitizers.",
    no_args_is_help=True,
)
vault_app.add_typer(sanitize_app, name="sanitize")

from vaultspec_core.cli.plan_cmd import plan_app  # noqa: E402

vault_app.add_typer(plan_app, name="plan")


# ---- vault add ---------------------------------------------------------------


@vault_app.command("add")
def cmd_add(
    doc_type: Annotated[str, typer.Argument(help="Document type to create")],
    feature: Annotated[
        str, typer.Option("--feature", "-f", help="Feature tag (kebab-case)")
    ] = "",
    date: Annotated[
        str | None, typer.Option("--date", help="Override date (YYYY-MM-DD)")
    ] = None,
    title: Annotated[str | None, typer.Option("--title", help="Document title")] = None,
    related: Annotated[
        list[str] | None,
        typer.Option(
            "--related",
            "-r",
            help=(
                "Related document(s). Accepts absolute path, relative path, "
                "filename, or stem. Resolved to [[wiki-link]] format."
            ),
        ),
    ] = None,
    tags: Annotated[
        list[str] | None,
        typer.Option(
            "--tags",
            help="Additional tags beyond the required directory and feature tags.",
        ),
    ] = None,
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing document")
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Preview without writing")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Create a new .vault/ document from a template.

    Supported types: adr, audit, exec, plan, reference, research.
    """
    apply_target(target)
    import re
    from datetime import UTC, datetime

    from vaultspec_core.console import get_console
    from vaultspec_core.core.types import get_context as _get_ctx
    from vaultspec_core.vaultcore.hydration import create_vault_doc
    from vaultspec_core.vaultcore.models import DocType
    from vaultspec_core.vaultcore.resolve import (
        RelatedResolutionError,
        resolve_related_inputs,
        validate_feature_dependencies,
    )

    console = get_console()

    # Resolve doc type enum
    try:
        dt = DocType(doc_type)
    except ValueError:
        # Index is auto-generated and is not user-creatable; surface
        # it explicitly as a non-option here so the error message
        # matches the rest of the docs surface.
        valid = ", ".join(d.value for d in DocType if d is not DocType.INDEX)
        console.print(
            f"[red]Unknown document type '{doc_type}'. Valid types: {valid}[/red]"
        )
        raise typer.Exit(code=1) from None
    if dt is DocType.INDEX:
        console.print(
            "[red]'index' documents are auto-generated. "
            "Use 'vaultspec-core vault feature index' instead of "
            "'vaultspec-core vault add index'.[/red]"
        )
        raise typer.Exit(code=1)

    # Validate feature tag
    feat = feature.lstrip("#").strip()
    if not feat:
        console.print("[red]--feature / -f is required (e.g. -f my-feature)[/red]")
        raise typer.Exit(code=1)
    if not re.match(r"^[a-z0-9][a-z0-9-]*$", feat):
        console.print(
            f"[red]Invalid feature tag '{feat}'. "
            "Must be kebab-case (lowercase, digits, hyphens).[/red]"
        )
        raise typer.Exit(code=1)

    # Default date to today (UTC so vault doc dates stay deterministic
    # across runners regardless of the operator's local timezone).
    date_str = date or datetime.now(UTC).strftime("%Y-%m-%d")

    # Validate extra tags format
    extra_tags: list[str] | None = None
    if tags:
        extra_tags = []
        for tag in tags:
            normalized = tag.lstrip("#").strip()
            if not re.match(r"^[a-z0-9][a-z0-9-]*$", normalized):
                console.print(
                    f"[red]Invalid tag '{tag}'. "
                    "Must be kebab-case (lowercase, digits, hyphens).[/red]"
                )
                raise typer.Exit(code=1)
            extra_tags.append(f"#{normalized}")

    # Resolve related paths to wiki-links
    resolved_related: list[str] | None = None
    if related:
        try:
            resolved_related = resolve_related_inputs(related, _get_ctx().target_dir)
        except RelatedResolutionError as exc:
            for failure in exc.failures:
                console.print(
                    f"[red]Cannot resolve related document: '{failure}'[/red]"
                )
            console.print(
                "[dim]Accepted formats: absolute path, relative path, "
                "filename, stem, or [[wiki-link]][/dim]"
            )
            raise typer.Exit(code=1) from None

    # Validate feature dependencies (lifecycle rules)
    dep_diagnostics = validate_feature_dependencies(_get_ctx().target_dir, dt, feat)
    has_errors = False
    for diag in dep_diagnostics:
        if diag.startswith("ERROR:"):
            console.print(f"[red]{diag}[/red]")
            has_errors = True
        elif diag.startswith("WARNING:"):
            console.print(f"[yellow]{diag}[/yellow]")
    if has_errors:
        raise typer.Exit(code=1)

    try:
        path = create_vault_doc(
            root_dir=_get_ctx().target_dir,
            doc_type=dt,
            feature=feat,
            date_str=date_str,
            title=title,
            related=resolved_related,
            extra_tags=extra_tags,
            force=force,
            dry_run=dry_run,
        )
    except FileNotFoundError as exc:
        _handle_error(exc)
        return
    except Exception as exc:
        _handle_error(exc)
        return

    if dry_run:
        console.print(f"[dim]Would create:[/dim] {path}")
        if json_output:
            import json

            typer.echo(
                json.dumps(
                    {
                        "path": str(path),
                        "type": doc_type,
                        "name": path.stem,
                        "dry_run": True,
                    },
                    indent=2,
                )
            )
        raise typer.Exit(0)

    # Post-creation self-validation
    _validate_created_doc(console, path, _get_ctx().target_dir)
    if json_output:
        import json

        typer.echo(
            json.dumps(
                {"path": str(path), "type": doc_type, "name": path.stem}, indent=2
            )
        )
        raise typer.Exit(0)
    console.print(f"[green]Created:[/green] {path}")


def _validate_created_doc(console: Console, doc_path, root_dir) -> None:
    """Run frontmatter validation on a newly created document.

    Prints warnings if the created document fails the project's own
    linting standards but does not block creation.
    """
    from vaultspec_core.vaultcore.parser import parse_vault_metadata

    try:
        content = doc_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return

    metadata, _ = parse_vault_metadata(content)
    errors = metadata.validate()
    if errors:
        console.print("[yellow]Post-creation validation warnings:[/yellow]")
        for err in errors:
            console.print(f"  [yellow]{err}[/yellow]")


# ---- vault stats -------------------------------------------------------------


@vault_app.command("stats")
def cmd_stats(
    feature: Annotated[
        str | None, typer.Option("--feature", "-f", help="Filter by feature tag")
    ] = None,
    date: Annotated[
        str | None, typer.Option("--date", help="Filter by date (YYYY-MM-DD)")
    ] = None,
    type_filter: Annotated[
        str | None, typer.Option("--type", help="Filter by document type")
    ] = None,
    invalid: Annotated[
        bool, typer.Option("--invalid", help="Show only invalid documents")
    ] = False,
    orphaned: Annotated[
        bool, typer.Option("--orphaned", help="Show only orphaned documents")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Show vault statistics and metrics."""
    apply_target(target)
    from vaultspec_core.console import get_console
    from vaultspec_core.core.types import get_context as _get_ctx
    from vaultspec_core.vaultcore.query import get_stats

    console = get_console()
    try:
        stats = get_stats(
            _get_ctx().target_dir, feature=feature, doc_type=type_filter, date=date
        )
    except OSError as exc:
        console.print(f"[red]Error reading vault: {exc}[/red]")
        raise typer.Exit(code=1) from exc
    if json_output:
        import json

        typer.echo(json.dumps(stats, indent=2, default=str))
        raise typer.Exit(0)
    console.print("[bold]Vault Statistics[/bold]")
    console.print(f"  Total documents: {stats['total_docs']}")
    console.print(f"  Total features:  {stats['total_features']}")
    if stats["counts_by_type"]:
        console.print("  By type:")
        for dt, count in sorted(stats["counts_by_type"].items()):
            console.print(f"    {dt}: {count}")
    if orphaned or invalid:
        if orphaned:
            console.print(f"  Orphaned docs: {stats['orphaned_count']}")
        if invalid:
            console.print(f"  Dangling links: {stats['dangling_link_count']}")


# ---- vault list --------------------------------------------------------------


@vault_app.command("list")
def cmd_list(
    doc_type: Annotated[
        str | None, typer.Argument(help="Document type to list")
    ] = None,
    date: Annotated[
        str | None, typer.Option("--date", help="Filter by date (YYYY-MM-DD)")
    ] = None,
    feature: Annotated[
        str | None, typer.Option("--feature", "-f", help="Filter by feature tag")
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """List vault documents, optionally filtered by type."""
    apply_target(target)
    from vaultspec_core.console import get_console
    from vaultspec_core.core.types import get_context as _get_ctx
    from vaultspec_core.vaultcore.models import DocType
    from vaultspec_core.vaultcore.query import list_documents

    console = get_console()

    # Validate doc_type and give helpful suggestions
    valid_types = {dt.value for dt in DocType} | {"orphaned", "invalid"}
    if doc_type and doc_type not in valid_types:
        if doc_type in ("features", "feature"):
            console.print(
                f"[yellow]'{doc_type}' is not a document type. "
                "Use [bold]vaultspec-core vault feature list[/bold] "
                "to list features.[/yellow]"
            )
            raise typer.Exit(code=1)
        console.print(
            f"[red]Unknown document type '{doc_type}'.[/red]\n"
            f"  Valid types: {', '.join(sorted(valid_types))}"
        )
        raise typer.Exit(code=1)

    try:
        docs = list_documents(
            _get_ctx().target_dir, doc_type=doc_type, feature=feature, date=date
        )
    except OSError as exc:
        console.print(f"[red]Error reading vault: {exc}[/red]")
        raise typer.Exit(code=1) from exc
    if json_output:
        import dataclasses
        import json

        typer.echo(
            json.dumps([dataclasses.asdict(d) for d in docs], indent=2, default=str)
        )
        raise typer.Exit(0)
    if not docs:
        console.print("[dim]No documents found.[/dim]")
        return
    for d in docs:
        parts = [f"[bold]{d.name}[/bold]"]
        parts.append(f"[dim]{d.doc_type}[/dim]")
        if d.feature:
            parts.append(f"#{d.feature}")
        if d.date:
            parts.append(d.date)
        console.print("  ".join(parts))


# ---- vault graph ------------------------------------------------------------


@graph_app.callback(invoke_without_command=True)
def cmd_graph(
    ctx: typer.Context,
    feature: Annotated[
        str | None,
        typer.Option(
            "--feature",
            "-f",
            help="Scope to a single feature",
        ),
    ] = None,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Output graph as JSON"),
    ] = False,
    metrics: Annotated[
        bool,
        typer.Option("--metrics", "-m", help="Show metrics"),
    ] = False,
    ascii_graph: Annotated[
        bool,
        typer.Option(
            "--ascii",
            help="Render graph topology via phart",
        ),
    ] = False,
    include_body: Annotated[
        bool,
        typer.Option("--body", help="Include body in JSON"),
    ] = False,
    target: TargetOption = None,
) -> None:
    """Render the vault document graph.

    Default output is a Rich hierarchical tree grouped by feature and
    type.  Use --ascii for a phart ASCII topology rendering, --json
    for networkx node-link JSON export, or --metrics for aggregate
    statistics computed by networkx algorithms.
    """
    if ctx.invoked_subcommand is not None:
        return

    apply_target(target)
    from vaultspec_core.console import get_console
    from vaultspec_core.core.types import get_context as _get_ctx
    from vaultspec_core.graph import VaultGraph

    console = get_console()
    try:
        graph = VaultGraph(_get_ctx().target_dir)
    except OSError as exc:
        console.print(f"[red]Error reading vault: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    if not graph.nodes:
        console.print("[dim]No vault documents found.[/dim]")
        raise typer.Exit(code=0)

    if as_json:
        console.print_json(
            graph.to_json(
                feature=feature,
                include_body=include_body,
            ),
        )
        return

    if metrics:
        _print_metrics(console, graph, feature=feature)
        return

    if ascii_graph:
        console.print(graph.render_ascii(feature=feature))
        return

    # Default: Rich hierarchical tree
    tree = graph.render_tree(feature=feature)
    console.print(tree)


def _print_metrics(
    console: Console,
    graph: VaultGraph,
    feature: str | None = None,
) -> None:
    """Render graph metrics as Rich tables."""
    from rich.table import Table

    m = graph.metrics(feature=feature)

    title = f"Graph Metrics - #{feature}" if feature else "Graph Metrics"
    console.print(f"\n[bold]{title}[/bold]\n")

    table = Table(
        show_header=False,
        box=None,
        padding=(0, 2),
    )
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")

    table.add_row("Documents", str(m.total_nodes))
    table.add_row("Edges", str(m.total_edges))
    table.add_row("Features", str(m.total_features))
    table.add_row("Total words", f"{m.total_words:,}")
    table.add_row("Density", f"{m.density:.4f}")
    table.add_row("Avg in-degree", f"{m.avg_in_degree:.2f}")
    table.add_row("Avg out-degree", f"{m.avg_out_degree:.2f}")
    if m.max_in_degree[1]:
        n, c = m.max_in_degree
        table.add_row("Max in-degree", f"{c}  ({n})")
    if m.max_out_degree[1]:
        n, c = m.max_out_degree
        table.add_row("Max out-degree", f"{c}  ({n})")
    table.add_row("Orphans", str(m.orphan_count))
    table.add_row("Phantoms", str(m.phantom_count))
    table.add_row("Dangling links", str(m.dangling_link_count))
    table.add_row("Components", str(m.connected_components))

    console.print(table)

    if m.nodes_by_type:
        console.print("\n[bold]By type[/bold]")
        for dt, count in m.nodes_by_type.items():
            console.print(f"  {dt}: {count}")

    if m.nodes_by_feature and not feature:
        console.print("\n[bold]By feature[/bold]")
        for feat, count in m.nodes_by_feature.items():
            console.print(f"  #{feat}: {count}")

    if m.in_degree_centrality:
        console.print("\n[bold]In-degree centrality (top 10)[/bold]")
        for name, score in m.in_degree_centrality.items():
            console.print(f"  {name}: {score:.4f}")

    if m.betweenness_centrality:
        console.print("\n[bold]Betweenness centrality (top 10)[/bold]")
        for name, score in m.betweenness_centrality.items():
            console.print(f"  {name}: {score:.4f}")


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


def _render_and_exit(
    result: CheckResult, verbose: bool, json_output: bool = False
) -> None:
    """Render a CheckResult and exit with appropriate code."""
    if json_output:
        import dataclasses
        import json

        typer.echo(json.dumps(dataclasses.asdict(result), indent=2, default=str))
        raise typer.Exit(code=1 if result.error_count else 0)
    from vaultspec_core.console import get_console
    from vaultspec_core.vaultcore.checks import render_check_result

    console = get_console()
    render_check_result(console, result, verbose=verbose)
    if result.error_count:
        raise typer.Exit(code=1)


# ---- vault repair -----------------------------------------------------------


@vault_app.command("repair")
def cmd_repair(
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview repair actions without writing"),
    ] = False,
    include_index: Annotated[
        bool,
        typer.Option(
            "--include-index/--no-index",
            help="Refresh generated feature indexes during repair.",
        ),
    ] = True,
    feature: Annotated[
        str | None,
        typer.Option("--feature", "-f", help="Scope repair to one feature tag"),
    ] = None,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Show INFO-level diagnostics")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Run the operator repair pipeline for vault content.

    The repair pipeline is broader than ``vault check all --fix``: it
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
    if json_output:
        import json

        typer.echo(json.dumps(_repair_payload(run), indent=2, default=str))
        raise typer.Exit(code=1 if run.error_count else 0)

    _render_repair_run(run, verbose=verbose)
    if run.error_count:
        raise typer.Exit(code=1)


def _repair_payload(run: RepairRun) -> dict:
    """Convert a :class:`RepairRun` to a JSON-serializable mapping."""
    return {
        "dry_run": run.dry_run,
        "feature": run.feature,
        "include_index": run.include_index,
        "phases": run.phases,
        "changed_files": run.changed_files,
        "generated_indexes": run.generated_indexes,
        "planned_fixes": run.planned_fixes,
        "unresolved": run.unresolved,
        "root_causes": run.root_causes,
        "error_count": run.error_count,
        "warning_count": run.warning_count,
        "fixed_count": run.fixed_count,
    }


def _render_repair_run(run: RepairRun, *, verbose: bool = False) -> None:
    """Render a repair run for human operators."""
    from vaultspec_core.console import get_console

    console = get_console()
    title = "Vault Repair Preview" if run.dry_run else "Vault Repair"
    if run.feature:
        title += f" - #{run.feature}"
    console.print(f"[bold]{title}[/bold]")

    for phase in run.phases:
        name = phase.get("phase", "unknown")
        if name == "preflight":
            status = phase.get("migration_status", "unknown")
            pending = phase.get("pending_migrations", [])
            platform = phase.get("platform", {})
            case_probe = platform.get("case_sensitive_probe", "unknown")
            console.print(f"  [bold]preflight[/bold]: migrations {status}")
            console.print(f"    filesystem case probe: {case_probe}")
            if pending:
                console.print(f"    pending migrations: {', '.join(pending)}")
            for migration in phase.get("applied_migrations", []):
                console.print(f"    applied migration: {migration['summary']}")
            if phase.get("message"):
                console.print(f"    [yellow]{phase['message']}[/yellow]")
        elif name in {"check", "fix", "postcheck"}:
            errors = phase.get("error_count", 0)
            warnings = phase.get("warning_count", 0)
            fixed = phase.get("fixed_count", 0)
            summary = f"{errors} errors, {warnings} warnings"
            if fixed:
                summary += f", {fixed} fixed"
            if phase.get("dry_run"):
                summary += ", preview only"
            console.print(f"  [bold]{name}[/bold]: {summary}")
            if verbose:
                _render_phase_diagnostics(console, phase)
        elif name == "index":
            if phase.get("skipped"):
                console.print(f"  [bold]index[/bold]: skipped ({phase.get('reason')})")
            elif phase.get("dry_run"):
                planned = phase.get("planned", [])
                console.print(f"  [bold]index[/bold]: {len(planned)} planned")
                if verbose:
                    for path in planned:
                        console.print(f"    {path}")
            else:
                generated = phase.get("generated", [])
                console.print(f"  [bold]index[/bold]: {len(generated)} refreshed")
                if verbose:
                    for path in generated:
                        console.print(f"    {path}")
        elif name == "summary":
            changed = phase.get("changed_files", [])
            unresolved = phase.get("unresolved_count", 0)
            console.print(f"  [bold]summary[/bold]: {len(changed)} changed files")
            console.print(f"    unresolved diagnostics: {unresolved}")

    if run.planned_fixes and run.dry_run:
        console.print()
        console.print(
            f"[bold]Planned mechanical fixes[/bold] ({len(run.planned_fixes)})"
        )
        for item in run.planned_fixes[:20]:
            path = f"{item['path']}: " if item.get("path") else ""
            console.print(f"  - {path}{item['fix_description'] or item['message']}")
        if len(run.planned_fixes) > 20:
            console.print(f"  ... {len(run.planned_fixes) - 20} more")

    if run.root_causes:
        console.print()
        console.print("[bold]Root-cause groups[/bold]")
        for group in run.root_causes:
            console.print(f"  - {group['root_cause']}: {group['count']}")

    if run.changed_files:
        console.print()
        console.print("[bold]Changed files[/bold]")
        for path in run.changed_files[:30]:
            console.print(f"  - {path}")
        if len(run.changed_files) > 30:
            console.print(f"  ... {len(run.changed_files) - 30} more")

    if run.unresolved:
        console.print()
        console.print("[bold]Unresolved work[/bold]")
        severity_rank = {"error": 0, "warning": 1, "info": 2}
        display_items = [
            item for item in run.unresolved if verbose or item.get("severity") != "info"
        ]
        display_items.sort(
            key=lambda item: severity_rank.get(str(item.get("severity")), 3)
        )
        for item in display_items[:20]:
            path = f"{item['path']}: " if item.get("path") else ""
            console.print(f"  - [{item['severity']}] {path}{item['message']}")
        if not display_items:
            console.print(
                "  INFO diagnostics hidden; rerun with --verbose to show them."
            )
        if len(display_items) > 20:
            console.print(f"  ... {len(display_items) - 20} more")


def _render_phase_diagnostics(console, phase: dict) -> None:
    for check in phase.get("checks", []):
        diagnostics = check.get("diagnostics", [])
        if not diagnostics:
            continue
        console.print(f"    {check['check_name']}:")
        for diag in diagnostics[:10]:
            path = f"{diag['path']}: " if diag.get("path") else ""
            console.print(f"      - [{diag['severity']}] {path}{diag['message']}")


@check_app.command("all")
def cmd_check_all(
    fix: Annotated[
        bool, typer.Option("--fix", help="Apply safe auto-corrections to vault content")
    ] = False,
    feature: Annotated[
        str | None, typer.Option("--feature", "-f", help="Filter by feature tag")
    ] = None,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Show INFO-level diagnostics")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Run all vault health checks."""
    apply_target(target)
    from vaultspec_core.console import get_console
    from vaultspec_core.core.types import get_context as _get_ctx
    from vaultspec_core.vaultcore.checks import render_check_result, run_all_checks

    console = get_console()
    results = run_all_checks(_get_ctx().target_dir, feature=feature, fix=fix)

    if json_output:
        import dataclasses
        import json

        typer.echo(
            json.dumps([dataclasses.asdict(r) for r in results], indent=2, default=str)
        )
        raise typer.Exit(0 if all(r.error_count == 0 for r in results) else 1)

    console.print("[bold]Vault Check  - All[/bold]")
    for r in results:
        render_check_result(console, r, verbose=verbose)

    total_errors = sum(r.error_count for r in results)
    total_warnings = sum(r.warning_count for r in results)
    total_fixed = sum(r.fixed_count for r in results)

    console.print()
    parts = []
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
def cmd_check_body_links(
    feature: Annotated[
        str | None, typer.Option("--feature", "-f", help="Filter by feature tag")
    ] = None,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Show INFO-level diagnostics")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Find wiki-links and markdown path links in document body text."""
    apply_target(target)
    from vaultspec_core.core.types import get_context as _get_ctx
    from vaultspec_core.graph import VaultGraph
    from vaultspec_core.vaultcore.checks import check_body_links

    graph = VaultGraph(_get_ctx().target_dir)
    snapshot = graph.to_snapshot()
    result = check_body_links(_get_ctx().target_dir, snapshot=snapshot, feature=feature)
    _render_and_exit(result, verbose, json_output=json_output)


@check_app.command("annotations")
def cmd_check_annotations(
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
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Find generated template annotations in vault documents."""
    apply_target(target)
    from vaultspec_core.core.types import get_context as _get_ctx
    from vaultspec_core.vaultcore.checks import check_annotations

    result = check_annotations(_get_ctx().target_dir, feature=feature, fix=fix)
    _render_and_exit(result, verbose, json_output=json_output)


@sanitize_app.command("annotations")
def cmd_sanitize_annotations(
    feature: Annotated[
        str | None, typer.Option("--feature", "-f", help="Filter by feature tag")
    ] = None,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Show stripped files")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Strip generated template annotations from vault documents."""
    apply_target(target)
    from vaultspec_core.core.types import get_context as _get_ctx
    from vaultspec_core.vaultcore.checks import check_annotations

    result = check_annotations(_get_ctx().target_dir, feature=feature, fix=True)
    _render_and_exit(result, verbose, json_output=json_output)


@check_app.command("dangling")
def cmd_check_dangling(
    fix: Annotated[
        bool, typer.Option("--fix", help="Apply safe auto-corrections to vault content")
    ] = False,
    feature: Annotated[
        str | None, typer.Option("--feature", "-f", help="Filter by feature tag")
    ] = None,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Show INFO-level diagnostics")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
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
    _render_and_exit(result, verbose, json_output=json_output)


@check_app.command("orphans")
def cmd_check_orphans(
    fix: Annotated[
        bool, typer.Option("--fix", help="Apply safe auto-corrections to vault content")
    ] = False,
    feature: Annotated[
        str | None, typer.Option("--feature", "-f", help="Filter by feature tag")
    ] = None,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Show INFO-level diagnostics")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
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
    _render_and_exit(result, verbose, json_output=json_output)


@check_app.command("frontmatter")
def cmd_check_frontmatter(
    fix: Annotated[
        bool, typer.Option("--fix", help="Apply safe auto-corrections to vault content")
    ] = False,
    feature: Annotated[
        str | None, typer.Option("--feature", "-f", help="Filter by feature tag")
    ] = None,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Show INFO-level diagnostics")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
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
    _render_and_exit(result, verbose, json_output=json_output)


@check_app.command("links")
def cmd_check_links(
    fix: Annotated[
        bool, typer.Option("--fix", help="Apply safe auto-corrections to vault content")
    ] = False,
    feature: Annotated[
        str | None, typer.Option("--feature", "-f", help="Filter by feature tag")
    ] = None,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Show INFO-level diagnostics")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
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
    _render_and_exit(result, verbose, json_output=json_output)


@check_app.command("features")
def cmd_check_features(
    fix: Annotated[
        bool, typer.Option("--fix", help="Apply safe auto-corrections to vault content")
    ] = False,
    feature: Annotated[
        str | None, typer.Option("--feature", "-f", help="Filter by feature tag")
    ] = None,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Show INFO-level diagnostics")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
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
    result = check_features(_get_ctx().target_dir, snapshot=snapshot, feature=feature)
    _render_and_exit(result, verbose, json_output=json_output)


@check_app.command("references")
def cmd_check_references(
    fix: Annotated[
        bool, typer.Option("--fix", help="Apply safe auto-corrections to vault content")
    ] = False,
    feature: Annotated[
        str | None, typer.Option("--feature", "-f", help="Filter by feature tag")
    ] = None,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Show INFO-level diagnostics")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
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
    _render_and_exit(result, verbose, json_output=json_output)


@check_app.command("schema")
def cmd_check_schema(
    fix: Annotated[
        bool, typer.Option("--fix", help="Apply safe auto-corrections to vault content")
    ] = False,
    feature: Annotated[
        str | None, typer.Option("--feature", "-f", help="Filter by feature tag")
    ] = None,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Show INFO-level diagnostics")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Enforce schema rules: ADRs must ref research, plans must ref ADRs."""
    apply_target(target)
    from vaultspec_core.core.types import get_context as _get_ctx
    from vaultspec_core.graph import VaultGraph
    from vaultspec_core.vaultcore.checks import check_schema

    graph = VaultGraph(_get_ctx().target_dir)
    result = check_schema(_get_ctx().target_dir, graph=graph, feature=feature, fix=fix)
    _render_and_exit(result, verbose, json_output=json_output)


@check_app.command("structure")
def cmd_check_structure(
    fix: Annotated[
        bool, typer.Option("--fix", help="Apply safe auto-corrections to vault content")
    ] = False,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Show INFO-level diagnostics")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
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
    _render_and_exit(result, verbose, json_output=json_output)


# ---- vault feature list ------------------------------------------------------


@feature_app.command("list")
def cmd_feature_list(
    date: Annotated[str | None, typer.Option("--date", help="Filter by date")] = None,
    orphaned: Annotated[
        bool, typer.Option("--orphaned", help="Show only orphaned features")
    ] = False,
    type_filter: Annotated[
        str | None, typer.Option("--type", help="Filter by document type")
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """List all feature tags in the vault."""
    apply_target(target)
    from vaultspec_core.console import get_console
    from vaultspec_core.core.types import get_context as _get_ctx
    from vaultspec_core.vaultcore.query import list_feature_details

    features = list_feature_details(
        _get_ctx().target_dir, date=date, doc_type=type_filter, orphaned_only=orphaned
    )
    console = get_console()
    if json_output:
        import json

        typer.echo(json.dumps(features, indent=2, default=str))
        raise typer.Exit(0)
    if not features:
        console.print("[dim]No features found.[/dim]")
        return
    for f in features:
        types_str = ", ".join(f["types"])
        plan_marker = " [green]plan[/green]" if f["has_plan"] else ""
        name = f["name"]
        count = f["doc_count"]
        console.print(
            f"  [bold]{name}[/bold]  {count} docs  ({types_str}){plan_marker}"
        )


# ---- vault feature index -----------------------------------------------------


@feature_app.command("index")
def cmd_feature_index(
    feature: Annotated[
        str | None,
        typer.Option("--feature", "-f", help="Generate index for a specific feature"),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Generate or update feature index documents.

    Writes a ``<feature>.index.md`` into ``.vault/index/`` for each
    feature tag (or a specific one with ``--feature``). Each index links
    to all documents sharing that feature tag, making implicit feature
    clusters explicit in the graph.
    """
    apply_target(target)
    from vaultspec_core.console import get_console
    from vaultspec_core.core.types import get_context as _get_ctx
    from vaultspec_core.graph import VaultGraph
    from vaultspec_core.vaultcore.index import generate_feature_index

    console = get_console()
    root_dir = _get_ctx().target_dir
    graph = VaultGraph(root_dir)

    features = [feature.lstrip("#")] if feature else graph.get_features()

    if not features:
        console.print("[dim]No features found in vault.[/dim]")
        return

    generated_paths: list = []
    for feat in features:
        nodes = graph.get_feature_nodes(feat)
        if not nodes:
            if not json_output:
                console.print(f"[dim]No documents found for #{feat}.[/dim]")
            continue
        path = generate_feature_index(root_dir, feat, nodes=nodes)
        generated_paths.append(path)
        if not json_output:
            console.print(f"[green]Index:[/green] {path}")

    if json_output:
        import json

        typer.echo(
            json.dumps({"generated": [str(p) for p in generated_paths]}, indent=2)
        )
        raise typer.Exit(0)


# ---- vault feature archive ---------------------------------------------------


@feature_app.command("archive")
def cmd_feature_archive(
    feature_tag: Annotated[str, typer.Argument(help="Feature tag to archive")],
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Archive all documents for a feature tag."""
    apply_target(target)
    from vaultspec_core.console import get_console
    from vaultspec_core.core.types import get_context as _get_ctx
    from vaultspec_core.vaultcore.query import archive_feature

    result = archive_feature(_get_ctx().target_dir, feature_tag)
    console = get_console()
    if json_output:
        import json

        typer.echo(json.dumps(result, indent=2, default=str))
        raise typer.Exit(0)
    if result["archived_count"] == 0:
        console.print(f"[dim]No documents found for feature '{feature_tag}'.[/dim]")
    else:
        console.print(f"[green]Archived {result['archived_count']} documents.[/green]")
        for p in result["paths"]:
            console.print(f"  {p}")
