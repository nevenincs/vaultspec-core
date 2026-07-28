"""Vault command group  - create, query, graph, check, and audit ``.vault/`` records.

Sub-groups: ``vaultspec-core vault feature`` (:data:`feature_app`) and
``vaultspec-core vault check`` (:data:`check_app`). Delegates to
:mod:`vaultspec_core.vaultcore.query`, :mod:`vaultspec_core.vaultcore.hydration`,
:mod:`vaultspec_core.vaultcore.checks`, and :mod:`vaultspec_core.graph` for
all backend logic. Mounted onto :data:`.root.app` as the ``vault`` command group.

This module is the public surface: every command re-exports through it so no
import site outside the package changes. The ``vault check``/``vault sanitize``/
``vault repair`` verbs live in :mod:`vaultspec_core.cli.vault_check_cmd` and the
``vault feature`` verbs live in :mod:`vaultspec_core.cli.vault_feature_cmd`,
both registered here via the same ``register_*`` pattern used by
:mod:`vaultspec_core.cli.edit_cmd`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

import typer

from vaultspec_core.cli._app import make_app
from vaultspec_core.cli._errors import handle_error as _handle_error
from vaultspec_core.cli._target import TargetOption, apply_target

if TYPE_CHECKING:
    from pathlib import Path

    from rich.console import Console

    from vaultspec_core.graph.api import VaultGraph


vault_app = make_app(
    help="Create, query, and audit records in the .vault/ project history.",
    no_args_is_help=True,
)

feature_app = make_app(
    help="Manage vault feature tags",
    no_args_is_help=True,
)
vault_app.add_typer(feature_app, name="feature")

check_app = make_app(
    help="Run vault health checks with optional auto-fix",
    no_args_is_help=True,
)
vault_app.add_typer(check_app, name="check")

sanitize_app = make_app(
    help="Run explicit vault sanitizers",
    no_args_is_help=True,
)
vault_app.add_typer(sanitize_app, name="sanitize")

rule_app = make_app(
    help="Manage custom team-shared rules",
    no_args_is_help=True,
)
vault_app.add_typer(rule_app, name="rule")

adr_app = make_app(
    help="Manage Architecture Decision Records (ADRs)",
    no_args_is_help=True,
)
vault_app.add_typer(adr_app, name="adr")

from vaultspec_core.cli.plan_cmd import plan_app  # noqa: E402

vault_app.add_typer(plan_app, name="plan")

from vaultspec_core.cli.link_cmd import link_app  # noqa: E402

vault_app.add_typer(link_app, name="link")

from vaultspec_core.cli.exec_cmd import exec_app  # noqa: E402

vault_app.add_typer(exec_app, name="exec")

from vaultspec_core.cli.archive_cmd import archive_app  # noqa: E402

vault_app.add_typer(archive_app, name="archive")

from vaultspec_core.cli.edit_cmd import (  # noqa: E402
    register_edit_commands,
    register_rename_command,
)

register_edit_commands(vault_app)
register_rename_command(vault_app)

from vaultspec_core.cli.vault_check_cmd import (  # noqa: E402
    register_check_commands,
    register_repair_command,
    register_sanitize_commands,
)

register_check_commands(check_app)
register_sanitize_commands(sanitize_app)

from vaultspec_core.cli.vault_feature_cmd import register_feature_commands  # noqa: E402

register_feature_commands(feature_app)


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
    topic: Annotated[
        str | None,
        typer.Option(
            "--topic",
            help=(
                "Narrative filename infix (kebab-case) disambiguating a "
                "second document of the same type for a feature; produces "
                "{date}-{feature}-{topic}-{type}.md. Only valid for adr, audit, "
                "reference, and research documents."
            ),
        ),
    ] = None,
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
            help="Additional tags beyond the required directory and feature tags",
        ),
    ] = None,
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing document")
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Preview without writing")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    no_hints: Annotated[
        bool, typer.Option("--no-hints", help="Suppress next-step advisory hints")
    ] = False,
    tier: Annotated[
        str,
        typer.Option(
            "--tier",
            help=(
                "Plan tier (L1..L4). Default L1. Ignored for non-plan "
                "document types whose templates do not carry a tier field."
            ),
        ),
    ] = "L1",
    step: Annotated[
        str | None,
        typer.Option(
            "--step",
            help="Canonical ID or display path of step to scaffold",
        ),
    ] = None,
    all_steps: Annotated[
        bool,
        typer.Option(
            "--all-steps",
            help="Scaffold execution records for all steps in parent plan",
        ),
    ] = False,
    summary: Annotated[
        bool,
        typer.Option(
            "--summary",
            help="Scaffold a Phase summary (exec only; requires --phase)",
        ),
    ] = False,
    phase: Annotated[
        str | None,
        typer.Option(
            "--phase",
            help="Canonical Phase ID (e.g. P01) to summarise; used with --summary",
        ),
    ] = None,
    target: TargetOption = None,
) -> None:
    """Create a new .vault/ document from a template.

    Supported types: adr, audit, exec, plan, reference, research.
    """
    apply_target(target)
    from datetime import UTC, datetime

    from vaultspec_core.cli import _add_ops
    from vaultspec_core.console import get_console
    from vaultspec_core.core.types import get_context as _get_ctx
    from vaultspec_core.vaultcore.hydration import (
        DocumentIdentity,
        ExecBinding,
        ParentPlan,
        TemplateFields,
        WritePolicy,
        create_vault_doc,
    )
    from vaultspec_core.vaultcore.models import DocType

    console = get_console()
    root_dir = _get_ctx().target_dir

    dt = _add_ops.resolve_doc_type(console, doc_type)
    _add_ops.validate_step_flags(
        console, dt, step=step, all_steps=all_steps, summary=summary, phase=phase
    )
    _add_ops.validate_tier(console, dt, tier)
    topic_value = _add_ops.normalize_topic(console, dt, topic)
    feat = _add_ops.normalize_feature(console, feature)
    extra_tags = _add_ops.normalize_extra_tags(console, tags)
    resolved_related = _add_ops.resolve_related(console, related, root_dir)
    _add_ops.report_dependency_diagnostics(
        console, root_dir, dt, feat, json_output=json_output
    )

    # Default date to today (UTC for deterministic vault doc dates)
    date_str = date or datetime.now(UTC).strftime("%Y-%m-%d")

    identity = DocumentIdentity(
        doc_type=dt, feature=feat, date=date_str, topic=topic_value
    )
    fields = TemplateFields(
        title=title,
        related=resolved_related,
        extra_tags=extra_tags,
        tier=tier if dt is DocType.PLAN else None,
    )
    write = WritePolicy(force=force, dry_run=dry_run)
    exec_binding = ExecBinding(summary=summary)

    if dt is DocType.EXEC and (step is not None or all_steps or summary):
        from vaultspec_core.plan.parser import parse_plan

        parent_plan_doc = _add_ops.resolve_parent_plan(
            console, root_dir, feat, resolved_related
        )
        parsed_plan = parse_plan(parent_plan_doc.path)
        plan_stem_arg = parent_plan_doc.path.stem
        parent_plan = ParentPlan(
            date=parent_plan_doc.date or plan_stem_arg[:10], stem=plan_stem_arg
        )

        if all_steps:
            raise typer.Exit(
                code=_add_ops.scaffold_all_steps(
                    parsed_plan.steps,
                    root_dir=root_dir,
                    identity=identity,
                    fields=fields,
                    plan=parent_plan,
                    write=write,
                    json_output=json_output,
                )
            )
        if step is not None:
            target_step = _add_ops.resolve_step_row(console, parsed_plan, step)
            exec_binding = ExecBinding(
                plan=parent_plan,
                step_id=target_step.canonical_id,
                step_display_path=target_step.display_path,
                step_scope=target_step.scope,
                step_action=target_step.action,
                summary=summary,
            )
        else:
            # The "--summary requires --phase" validation above guarantees a
            # non-None phase id by the time this branch runs.
            assert phase is not None
            exec_binding = ExecBinding(
                plan=parent_plan,
                summary=summary,
                phase_display_path=_add_ops.resolve_phase_display_path(
                    console, parsed_plan, phase
                ),
            )

    elif dt is DocType.EXEC and not json_output:
        console.print(
            "[yellow]Deprecation Warning: Scaffolding a flat execution "
            "record without --step or --all-steps is deprecated and will "
            "be removed in a future release.[/yellow]"
        )

    # Single-document scaffolding path (legacy route or --step route)
    with _add_ops.suppress_logging(active=json_output):
        try:
            path = create_vault_doc(
                root_dir,
                identity,
                fields,
                exec_binding=exec_binding,
                write=write,
            )
        except Exception as exc:
            _handle_error(exc, json_output=json_output)
            return

    if dry_run:
        _add_ops.emit_add_result(
            console, path, doc_type, json_output=json_output, dry_run=True
        )
        raise typer.Exit(0)

    # Reaching here means create_vault_doc wrote the document: exceptions above
    # cause an early return and a dry-run preview already exited.
    from vaultspec_core.cli._cache_hook import invalidate_graph_cache

    invalidate_graph_cache(root_dir)

    # Post-creation self-validation
    _validate_created_doc(console, path)

    from vaultspec_core.cli.rendering import emit_next_step_hint

    context_vars = {
        "feature": feat,
        "research_stem": path.stem,
        "adr_stem": path.stem,
        "plan_stem": path.stem,
        "audit_stem": path.stem,
        "rule_name": f"{feat}-rule",
    }

    hint_dict = emit_next_step_hint(
        command=f"vault.add.{dt.value}",
        outcome="created",
        context_vars=context_vars,
        json_output=json_output,
        no_hints=no_hints,
    )

    _add_ops.emit_add_result(
        console, path, doc_type, json_output=json_output, hints=hint_dict
    )
    if json_output:
        raise typer.Exit(0)


def _validate_created_doc(console: Console, doc_path: Path) -> None:
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

        from vaultspec_core.cli.rendering import json_envelope

        typer.echo(
            json.dumps(
                json_envelope("vault.stats", "unchanged", stats),
                indent=2,
                default=str,
            )
        )
        raise typer.Exit(0)
    from vaultspec_core.cli.rendering import (
        Column,
        Field,
        render_listing,
        render_record,
        summary_line,
    )

    fields = [
        Field("total documents", str(stats["total_docs"])),
        Field("total features", str(stats["total_features"])),
    ]
    if orphaned:
        fields.append(Field("orphaned docs", str(stats["orphaned_count"])))
    if invalid:
        fields.append(Field("dangling links", str(stats["dangling_link_count"])))
    render_record(fields, title="Vault statistics")

    by_type = sorted(stats["counts_by_type"].items())
    if by_type:
        render_listing(
            [{"type": dt, "count": str(count)} for dt, count in by_type],
            [Column("type"), Column("count")],
            title="By type",
            summary=summary_line(sum(count for _, count in by_type), "documents"),
        )


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

        from vaultspec_core.cli.rendering import json_envelope

        typer.echo(
            json.dumps(
                json_envelope(
                    "vault.list",
                    "unchanged",
                    {"documents": [dataclasses.asdict(d) for d in docs]},
                ),
                indent=2,
                default=str,
            )
        )
        raise typer.Exit(0)
    from vaultspec_core.cli.rendering import (
        Cell,
        Column,
        render_listing,
        summary_line,
    )

    rows = [
        {
            "name": Cell(d.name, "bold"),
            "type": Cell(d.doc_type, "dim"),
            "feature": f"#{d.feature}" if d.feature else "",
            "date": d.date or "",
        }
        for d in docs
    ]
    render_listing(
        rows,
        [Column("name"), Column("type"), Column("feature"), Column("date")],
        title="Vault documents",
        summary=summary_line(len(docs), "documents"),
        empty="no documents found",
    )


# ---- vault graph ------------------------------------------------------------


@vault_app.command("graph")
def cmd_graph(
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
    node: Annotated[
        str | None,
        typer.Option(
            "--node",
            help="Scope the JSON graph to this node's local (ego) neighbourhood",
        ),
    ] = None,
    depth: Annotated[
        int,
        typer.Option(
            "--depth",
            help="Ego-graph radius in hops; only used with --node",
        ),
    ] = 1,
    derived: Annotated[
        bool,
        typer.Option(
            "--derived/--no-derived",
            help="Include the derived relatedness edge set in JSON output",
        ),
    ] = True,
    ref: Annotated[
        str | None,
        typer.Option(
            "--ref",
            help=(
                "Read the vault corpus from this git ref (branch/tag/sha) via "
                "the object database, without a working-tree checkout"
            ),
        ),
    ] = None,
    target: TargetOption = None,
) -> None:
    """Render the vault document graph.

    Default output is a Rich hierarchical tree grouped by feature and
    type.  Use --ascii for a phart ASCII topology rendering, --json
    for networkx node-link JSON export, or --metrics for aggregate
    statistics computed by networkx algorithms.

    For JSON output, --node <stem> with --depth N scopes the payload to a
    node's local (ego) neighbourhood, and --no-derived omits the derived
    relatedness edge set.

    Use --ref <branch|sha> to read the corpus from the git object database at
    that ref instead of the working tree (read-only; no checkout, no cache
    write). The JSON envelope stays ``vaultspec.vault.graph.v2`` with a
    top-level ``ref`` key naming the snapshot. A non-git workspace or an
    unresolvable ref fails with a typed error rather than a working-tree read.
    """
    apply_target(target)
    from vaultspec_core.console import get_console
    from vaultspec_core.core.types import get_context as _get_ctx
    from vaultspec_core.graph import VaultGraph
    from vaultspec_core.graph.refscan import RefScanError

    console = get_console()
    try:
        if ref is not None:
            graph = VaultGraph.from_ref(_get_ctx().target_dir, ref)
        else:
            graph = VaultGraph(_get_ctx().target_dir)
    except RefScanError as exc:
        console.print(f"[red]Error reading ref {ref!r}: {exc}[/red]")
        raise typer.Exit(code=1) from exc
    except OSError as exc:
        console.print(f"[red]Error reading vault: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    if as_json:
        import json

        from vaultspec_core.cli.rendering import json_envelope

        if node is not None and node not in graph.nodes:
            typer.echo(
                json.dumps(
                    json_envelope(
                        "vault.graph",
                        "failed",
                        {"message": f"Node not found: {node}"},
                        version=2,
                    ),
                    indent=2,
                    default=str,
                )
            )
            raise typer.Exit(code=1)

        envelope = json_envelope(
            "vault.graph",
            "unchanged",
            graph.to_dict(
                feature=feature,
                include_body=include_body,
                node=node,
                depth=depth,
                include_derived=derived,
            ),
            version=2,
        )
        typer.echo(json.dumps(envelope, indent=2, default=str))
        return

    if not graph.nodes:
        console.print("[dim]No vault documents found.[/dim]")
        raise typer.Exit(code=0)

    if metrics:
        _print_metrics(graph, feature=feature)
        return

    if ascii_graph:
        console.print(graph.render_ascii(feature=feature))
        return

    # Default: box-free hierarchical tree (renders directly).
    graph.render_tree(feature=feature)


def _print_metrics(
    graph: VaultGraph,
    feature: str | None = None,
) -> None:
    """Render graph metrics through the box-free Record and Listing shapes."""
    from vaultspec_core.cli.rendering import Field, render_record

    m = graph.metrics(feature=feature)

    title = f"Graph metrics - #{feature}" if feature else "Graph metrics"

    fields = [
        Field("documents", str(m.total_nodes)),
        Field("edges", str(m.total_edges)),
        Field("features", str(m.total_features)),
        Field("total_words", f"{m.total_words:,}"),
        Field("density", f"{m.density:.4f}"),
        Field("avg_in_degree", f"{m.avg_in_degree:.2f}"),
        Field("avg_out_degree", f"{m.avg_out_degree:.2f}"),
    ]
    if m.max_in_degree[1]:
        n, c = m.max_in_degree
        fields.append(Field("max_in_degree", f"{c} ({n})"))
    if m.max_out_degree[1]:
        n, c = m.max_out_degree
        fields.append(Field("max_out_degree", f"{c} ({n})"))
    fields += [
        Field("orphans", str(m.orphan_count)),
        Field("phantoms", str(m.phantom_count)),
        Field("dangling_links", str(m.dangling_link_count)),
        Field("components", str(m.connected_components)),
    ]

    render_record(fields, title=title)

    from vaultspec_core.cli.rendering import Column, render_listing, summary_line

    if m.nodes_by_type:
        render_listing(
            [{"type": dt, "count": str(c)} for dt, c in m.nodes_by_type.items()],
            [Column("type"), Column("count")],
            title="By type",
            summary=summary_line(sum(m.nodes_by_type.values()), "documents"),
        )

    if m.nodes_by_feature and not feature:
        render_listing(
            [
                {"feature": f"#{f}", "count": str(c)}
                for f, c in m.nodes_by_feature.items()
            ],
            [Column("feature"), Column("count")],
            title="By feature",
            summary=summary_line(len(m.nodes_by_feature), "features"),
        )

    if m.in_degree_centrality:
        render_listing(
            [
                {"document": n, "score": f"{s:.4f}"}
                for n, s in m.in_degree_centrality.items()
            ],
            [Column("document"), Column("score")],
            title="In-degree centrality (top 10)",
        )

    if m.betweenness_centrality:
        render_listing(
            [
                {"document": n, "score": f"{s:.4f}"}
                for n, s in m.betweenness_centrality.items()
            ],
            [Column("document"), Column("score")],
            title="Betweenness centrality (top 10)",
        )


register_repair_command(vault_app)


# ---- vault rule promote ------------------------------------------------------


@rule_app.command("promote")
def cmd_rule_promote(
    from_audit: Annotated[
        str, typer.Option("--from", help="Audit stem to promote from")
    ],
    as_rule: Annotated[
        str, typer.Option("--as", help="Kebab-case name of the promoted rule")
    ],
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing rule source")
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Preview without writing")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Promote an audit finding to a team-shared rule."""
    apply_target(target)
    import json

    from vaultspec_core.cli.rendering import json_envelope
    from vaultspec_core.console import get_console
    from vaultspec_core.core.exceptions import VaultSpecError
    from vaultspec_core.core.rules import rule_promote

    try:
        rule_file = rule_promote(
            from_audit=from_audit,
            rule_name=as_rule,
            force=force,
            dry_run=dry_run,
        )
    except (VaultSpecError, OSError) as exc:
        _handle_error(exc, json_output=json_output)
        return

    console = get_console()
    if json_output:
        status = "created" if not dry_run else "unchanged"
        typer.echo(
            json.dumps(
                json_envelope(
                    "vault.rule.promote",
                    status,
                    {"path": str(rule_file)},
                ),
                indent=2,
            )
        )
        raise typer.Exit(0)

    action = "Would promote rule" if dry_run else "Rule promoted successfully"
    console.print(f"[green]{action}:[/green] {rule_file}")


# ---- vault adr supersede -----------------------------------------------------


@adr_app.command("supersede")
def cmd_adr_supersede(
    old_adr: Annotated[str, typer.Argument(help="Old ADR stem to supersede")],
    by_new_adr: Annotated[
        str,
        typer.Option(
            "--by",
            help="New ADR stem that supersedes the old one",
        ),
    ] = "",
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Preview without writing")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Supersede an old ADR with a new ADR."""
    apply_target(target)
    import json

    from vaultspec_core.cli.rendering import json_envelope
    from vaultspec_core.console import get_console
    from vaultspec_core.core.adr import adr_supersede
    from vaultspec_core.core.exceptions import VaultSpecError

    console = get_console()

    if not by_new_adr:
        if json_output:
            typer.echo(
                json.dumps(
                    json_envelope(
                        "vault.adr.supersede",
                        "failed",
                        {"message": "--by option is required."},
                    ),
                    indent=2,
                )
            )
        else:
            console.print("[red]Error: --by option is required.[/red]")
        raise typer.Exit(code=1)

    try:
        old_file, new_file = adr_supersede(
            old_adr=old_adr,
            by_new_adr=by_new_adr,
            dry_run=dry_run,
        )
    except (VaultSpecError, OSError) as exc:
        _handle_error(exc, json_output=json_output)
        return

    if json_output:
        status = "updated" if not dry_run else "unchanged"
        typer.echo(
            json.dumps(
                json_envelope(
                    "vault.adr.supersede",
                    status,
                    {
                        "old_path": str(old_file),
                        "new_path": str(new_file),
                    },
                ),
                indent=2,
            )
        )
        raise typer.Exit(0)

    action = "Would supersede ADR" if dry_run else "ADR superseded successfully"
    console.print(f"[green]{action}:[/green] {old_file} by {new_file}")
