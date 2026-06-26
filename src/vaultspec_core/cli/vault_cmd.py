"""Vault command group  - create, query, graph, check, and audit ``.vault/`` records.

Sub-groups: ``vaultspec-core vault feature`` (:data:`feature_app`) and
``vaultspec-core vault check`` (:data:`check_app`). Delegates to
:mod:`vaultspec_core.vaultcore.query`, :mod:`vaultspec_core.vaultcore.hydration`,
:mod:`vaultspec_core.vaultcore.checks`, and :mod:`vaultspec_core.graph` for
all backend logic. Mounted onto :data:`.root.app` as the ``vault`` command group.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

import typer

from vaultspec_core.cli._app import make_app
from vaultspec_core.cli._errors import handle_error as _handle_error
from vaultspec_core.cli._target import TargetOption, apply_target

if TYPE_CHECKING:
    from rich.console import Console

    from vaultspec_core.graph.api import VaultGraph
    from vaultspec_core.vaultcore.checks._base import CheckResult
    from vaultspec_core.vaultcore.repair import RepairRun


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

from vaultspec_core.cli.edit_cmd import (  # noqa: E402
    register_edit_commands,
    register_rename_command,
)

register_edit_commands(vault_app)
register_rename_command(vault_app)


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

    # Validate step-aware flags
    if (step is not None or all_steps or summary) and dt is not DocType.EXEC:
        console.print(
            "[red]Error: --step, --all-steps, and --summary options are only "
            "valid when creating 'exec' documents.[/red]"
        )
        raise typer.Exit(code=1)

    if step is not None and all_steps:
        console.print(
            "[red]Error: --step and --all-steps options are mutually exclusive.[/red]"
        )
        raise typer.Exit(code=1)

    if summary and (step is not None or all_steps):
        console.print(
            "[red]Error: --summary cannot be combined with --step or --all-steps.[/red]"
        )
        raise typer.Exit(code=1)

    if summary and phase is None:
        console.print(
            "[red]Error: --summary requires --phase <P##> naming the Phase "
            "to summarise.[/red]"
        )
        raise typer.Exit(code=1)

    if phase is not None and not summary:
        console.print(
            "[red]Error: --phase is only valid together with --summary.[/red]"
        )
        raise typer.Exit(code=1)

    # Validate tier for plan documents
    if dt is DocType.PLAN and tier not in {"L1", "L2", "L3", "L4"}:
        console.print(
            f"[red]Invalid tier '{tier}'. Allowed values: L1, L2, L3, L4.[/red]"
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

    # Default date to today (UTC for deterministic vault doc dates)
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
    dep_errors = [d for d in dep_diagnostics if d.startswith("ERROR:")]

    if json_output:
        for diag in dep_diagnostics:
            if not diag.startswith("ERROR:"):
                typer.echo(diag, err=True)
        if dep_errors:
            import json

            from vaultspec_core.cli.rendering import json_envelope

            typer.echo(
                json.dumps(
                    json_envelope(
                        "vault.add", "failed", {"message": " ".join(dep_errors)}
                    ),
                    indent=2,
                )
            )
            raise typer.Exit(code=1)
    else:
        for diag in dep_diagnostics:
            style = "red" if diag.startswith("ERROR:") else "yellow"
            console.print(f"[{style}]{diag}[/{style}]")
        if dep_errors:
            raise typer.Exit(code=1)

    # Handle parent plan resolution if step-aware route is active
    plan_date_arg = None
    plan_stem_arg = None
    step_id_arg = None
    step_display_path_arg = None
    step_scope_arg = None
    step_action_arg = None
    phase_display_arg = None

    if dt is DocType.EXEC and (step is not None or all_steps or summary):
        from vaultspec_core.vaultcore.query import list_documents

        parent_plan_doc = None
        if resolved_related:
            for rel in resolved_related:
                stem = rel.lstrip("[").rstrip("]")
                plan_docs = list_documents(_get_ctx().target_dir, doc_type="plan")
                for doc in plan_docs:
                    if doc.path.stem == stem:
                        parent_plan_doc = doc
                        break
                if parent_plan_doc:
                    break

        if parent_plan_doc is None:
            plan_docs = list_documents(
                _get_ctx().target_dir, doc_type="plan", feature=feat
            )
            if len(plan_docs) == 1:
                parent_plan_doc = plan_docs[0]
            elif len(plan_docs) > 1:
                names = ", ".join(d.path.name for d in plan_docs)
                console.print(
                    f"[red]Multiple plans found for feature '{feat}': {names}. "
                    "Specify the parent plan using --related.[/red]"
                )
                raise typer.Exit(code=1)
            else:
                console.print(
                    f"[red]No plan found for feature '{feat}'. "
                    "Create a plan document before adding execution records.[/red]"
                )
                raise typer.Exit(code=1)

        from vaultspec_core.plan.parser import parse_plan

        parsed_plan = parse_plan(parent_plan_doc.path)
        plan_stem_arg = parent_plan_doc.path.stem
        plan_date_arg = parent_plan_doc.date or plan_stem_arg[:10]

        if step is not None:
            from vaultspec_core.plan.commands.step_ops import (
                AmbiguousStepError,
                StepNotFoundError,
                find_step,
            )

            try:
                target_step = find_step(parsed_plan, step)
            except StepNotFoundError as exc:
                console.print(f"[red]Error: {exc}[/red]")
                raise typer.Exit(code=1) from None
            except AmbiguousStepError as exc:
                console.print(f"[red]Error: {exc}[/red]")
                raise typer.Exit(code=1) from None

            step_id_arg = target_step.canonical_id
            step_display_path_arg = target_step.display_path
            step_scope_arg = target_step.scope
            step_action_arg = target_step.action

        elif summary:
            from vaultspec_core.plan.commands.phase_ops import (
                PhaseNotFoundError,
                find_phase,
            )

            # The "--summary requires --phase" validation above guarantees a
            # non-None phase id by the time this branch runs.
            assert phase is not None
            try:
                target_phase = find_phase(parsed_plan, phase)
            except PhaseNotFoundError as exc:
                console.print(f"[red]Error: {exc}[/red]")
                raise typer.Exit(code=1) from None

            phase_display_arg = target_phase.display_path

        elif all_steps:
            # Bulk scaffolding loop
            import logging

            from vaultspec_core.cli.rendering import Outcome, OutcomeItem, emit_outcomes

            items = []
            root_dir = _get_ctx().target_dir

            previous_logging_disable = logging.root.manager.disable
            if json_output:
                logging.disable(logging.CRITICAL)

            try:
                for s in parsed_plan.steps:
                    target_path = create_vault_doc(
                        root_dir=root_dir,
                        doc_type=dt,
                        feature=feat,
                        date_str=date_str,
                        title=title,
                        related=resolved_related,
                        extra_tags=extra_tags,
                        force=True,
                        dry_run=True,
                        step_id=s.canonical_id,
                        step_display_path=s.display_path,
                        step_scope=s.scope,
                        step_action=s.action,
                        plan_date=plan_date_arg,
                        plan_stem=plan_stem_arg,
                    )

                    rel_name = str(target_path.relative_to(root_dir))

                    if target_path.exists():
                        if not force:
                            items.append(
                                OutcomeItem(
                                    name=rel_name,
                                    outcome=Outcome.SKIPPED,
                                    detail="skipped; exists",
                                )
                            )
                            continue
                        else:
                            outcome_type = Outcome.UPDATED
                            detail_msg = (
                                "overwritten" if not dry_run else "would overwrite"
                            )
                    else:
                        outcome_type = Outcome.CREATED
                        detail_msg = "created" if not dry_run else "would create"

                    if not dry_run:
                        create_vault_doc(
                            root_dir=root_dir,
                            doc_type=dt,
                            feature=feat,
                            date_str=date_str,
                            title=title,
                            related=resolved_related,
                            extra_tags=extra_tags,
                            force=force,
                            dry_run=False,
                            step_id=s.canonical_id,
                            step_display_path=s.display_path,
                            step_scope=s.scope,
                            step_action=s.action,
                            plan_date=plan_date_arg,
                            plan_stem=plan_stem_arg,
                        )

                    items.append(
                        OutcomeItem(
                            name=rel_name,
                            outcome=outcome_type,
                            detail=detail_msg,
                        )
                    )
            finally:
                if json_output:
                    logging.disable(previous_logging_disable)

            if not dry_run and items:
                from vaultspec_core.cli._cache_hook import invalidate_graph_cache

                invalidate_graph_cache(root_dir)

            exit_code = emit_outcomes(
                items,
                command="vault.add",
                title="Scaffold Execution Steps",
                json_output=json_output,
            )
            raise typer.Exit(code=exit_code)

    elif dt is DocType.EXEC:
        if not json_output:
            console.print(
                "[yellow]Deprecation Warning: Scaffolding a flat execution "
                "record without --step or --all-steps is deprecated and will "
                "be removed in a future release.[/yellow]"
            )

    # Single-document scaffolding path (legacy route or --step route)
    import logging

    previous_logging_disable = logging.root.manager.disable
    if json_output:
        logging.disable(logging.CRITICAL)
    try:
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
                tier=tier if dt is DocType.PLAN else None,
                step_id=step_id_arg,
                step_display_path=step_display_path_arg,
                step_scope=step_scope_arg,
                step_action=step_action_arg,
                plan_date=plan_date_arg,
                plan_stem=plan_stem_arg,
                summary=summary,
                phase_display_path=phase_display_arg,
            )
        except FileNotFoundError as exc:
            _handle_error(exc, json_output=json_output)
            return
        except Exception as exc:
            _handle_error(exc, json_output=json_output)
            return
    finally:
        if json_output:
            logging.disable(previous_logging_disable)

    # Only invalidate when the doc was actually written (not a dry-run preview).
    # Exceptions above cause early return, so reaching here means create_vault_doc
    # completed successfully; dry_run=False implies a real write occurred.
    if not dry_run:
        from vaultspec_core.cli._cache_hook import invalidate_graph_cache

        invalidate_graph_cache(_get_ctx().target_dir)

    if dry_run:
        if json_output:
            import json

            from vaultspec_core.cli.rendering import json_envelope

            typer.echo(
                json.dumps(
                    json_envelope(
                        "vault.add",
                        "created",
                        {
                            "path": str(path),
                            "type": doc_type,
                            "name": path.stem,
                            "dry_run": True,
                        },
                    ),
                    indent=2,
                )
            )
        else:
            console.print(f"[dim]Would create:[/dim] {path}")
        raise typer.Exit(0)

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

    if json_output:
        import json

        from vaultspec_core.cli.rendering import json_envelope

        typer.echo(
            json.dumps(
                json_envelope(
                    "vault.add",
                    "created",
                    {"path": str(path), "type": doc_type, "name": path.stem},
                    hints=hint_dict,
                ),
                indent=2,
            )
        )
        raise typer.Exit(0)
    console.print(f"[green]Created:[/green] {path}")


def _validate_created_doc(console: Console, doc_path) -> None:
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
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
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

        from vaultspec_core.cli.rendering import json_envelope

        if run.error_count:
            repair_status = "failed"
        elif run.fixed_count:
            repair_status = "updated"
        else:
            repair_status = "unchanged"
        typer.echo(
            json.dumps(
                json_envelope("vault.repair", repair_status, _repair_payload(run)),
                indent=2,
                default=str,
            )
        )
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
        "partial_failure": run.partial_failure,
        "phases": run.phases,
        "journal": run.journal,
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
    if run.partial_failure:
        console.print("[red]  partial repair: at least one phase failed[/red]")

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
            if phase.get("partial_failure"):
                console.print("    [red]partial failure: true[/red]")
            if phase.get("journal_count"):
                console.print(f"    journal entries: {phase['journal_count']}")

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
        hidden_info = len(run.unresolved) - len(display_items)
        display_items.sort(
            key=lambda item: severity_rank.get(str(item.get("severity")), 3)
        )
        for item in display_items[:20]:
            path = f"{item['path']}: " if item.get("path") else ""
            console.print(f"  - [{item['severity']}] {path}{item['message']}")
        if hidden_info:
            console.print(
                f"  ... {hidden_info} INFO diagnostics hidden; "
                "rerun with --verbose to show them."
            )
        if len(display_items) > 20:
            console.print(f"  ... {len(display_items) - 20} more non-INFO diagnostics")


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
    _render_and_exit(
        result, verbose, json_output=json_output, command="vault.check.body-links"
    )


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
    _render_and_exit(
        result, verbose, json_output=json_output, command="vault.check.annotations"
    )


@check_app.command("markdown")
def cmd_check_markdown(
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
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Check and optionally fix markdown hygiene (trailing whitespace, blank
    runs, final newline)."""
    apply_target(target)
    from vaultspec_core.core.types import get_context as _get_ctx
    from vaultspec_core.vaultcore.checks import check_markdown

    result = check_markdown(_get_ctx().target_dir, feature=feature, fix=fix)
    _render_and_exit(
        result, verbose, json_output=json_output, command="vault.check.markdown"
    )


@check_app.command("placeholders")
def cmd_check_placeholders(
    feature: Annotated[
        str | None, typer.Option("--feature", "-f", help="Filter by feature tag")
    ] = None,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Show INFO-level diagnostics")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
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
        result, verbose, json_output=json_output, command="vault.check.placeholders"
    )


@sanitize_app.command("annotations")
def cmd_sanitize_annotations(
    feature: Annotated[
        str | None, typer.Option("--feature", "-f", help="Filter by feature tag")
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Preview annotation stripping")
    ] = False,
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

    if not json_output:
        from vaultspec_core.console import get_console

        console = get_console()
        console.print(
            "[yellow]Deprecation Warning: 'vaultspec-core vault sanitize annotations' "
            "is deprecated. Please use 'vaultspec-core vault check annotations --fix' "
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
    _render_and_exit(
        result, verbose, json_output=json_output, command="vault.check.dangling"
    )


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
    _render_and_exit(
        result, verbose, json_output=json_output, command="vault.check.orphans"
    )


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
    _render_and_exit(
        result, verbose, json_output=json_output, command="vault.check.frontmatter"
    )


@check_app.command("modified-stamp")
def cmd_check_modified_stamp(
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
        result, verbose, json_output=json_output, command="vault.check.modified-stamp"
    )


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
    _render_and_exit(
        result, verbose, json_output=json_output, command="vault.check.links"
    )


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
    _render_and_exit(
        result, verbose, json_output=json_output, command="vault.check.features"
    )


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
    _render_and_exit(
        result, verbose, json_output=json_output, command="vault.check.references"
    )


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
    _render_and_exit(
        result, verbose, json_output=json_output, command="vault.check.schema"
    )


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
    _render_and_exit(
        result, verbose, json_output=json_output, command="vault.check.structure"
    )


@check_app.command("rename-integrity")
def cmd_check_rename_integrity(
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
            help="Frontmatter-wins: physically rename file to match frontmatter name",
        ),
    ] = False,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Show INFO-level diagnostics")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
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
        result, verbose, json_output=json_output, command="vault.check.rename-integrity"
    )


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
    stale_days: Annotated[
        int | None,
        typer.Option(
            "--stale-days",
            help="Show only features whose latest activity is older than N days",
        ),
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
    if stale_days is not None:
        features = _filter_stale_features(features, stale_days)
    console = get_console()
    if json_output:
        import json

        from vaultspec_core.cli.rendering import json_envelope

        typer.echo(
            json.dumps(
                json_envelope(
                    "vault.feature.list", "unchanged", {"features": features}
                ),
                indent=2,
                default=str,
            )
        )
        raise typer.Exit(0)
    if not features:
        console.print("[dim]No features found.[/dim]")
        return
    for f in features:
        types_str = ", ".join(f["types"])
        plan_marker = " [green]plan[/green]" if f["has_plan"] else ""
        name = f["name"]
        count = f["doc_count"]
        latest = f.get("latest_activity")
        activity = f"  [dim]{latest}[/dim]" if latest else ""
        console.print(
            f"  [bold]{name}[/bold]  {count} docs  ({types_str}){plan_marker}{activity}"
        )


def _filter_stale_features(features: list[dict], stale_days: int) -> list[dict]:
    """Return features whose latest activity is older than *stale_days*.

    A feature with no parseable ``latest_activity`` is treated as stale so
    a sweep surfaces it rather than silently hiding undated work. The
    comparison is anchored on today's date.
    """
    import datetime as _dt

    from vaultspec_core.vaultcore.models import parse_lenient_date

    cutoff = _dt.date.today() - _dt.timedelta(days=stale_days)
    stale: list[dict] = []
    for feature in features:
        parsed = parse_lenient_date(feature.get("latest_activity"))
        if parsed is None or parsed < cutoff:
            stale.append(feature)
    return stale


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
        if json_output:
            import json

            from vaultspec_core.cli.rendering import json_envelope

            typer.echo(
                json.dumps(
                    json_envelope(
                        "vault.feature.index", "unchanged", {"generated": []}
                    ),
                    indent=2,
                )
            )
            raise typer.Exit(0)
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

    if generated_paths:
        from vaultspec_core.cli._cache_hook import invalidate_graph_cache

        invalidate_graph_cache(root_dir)

    if json_output:
        import json

        from vaultspec_core.cli.rendering import json_envelope

        index_status = "updated" if generated_paths else "unchanged"
        typer.echo(
            json.dumps(
                json_envelope(
                    "vault.feature.index",
                    index_status,
                    {"generated": [str(p) for p in generated_paths]},
                ),
                indent=2,
            )
        )
        raise typer.Exit(0)


# ---- vault feature archive ---------------------------------------------------


@feature_app.command("archive")
def cmd_feature_archive(
    feature_tag: Annotated[str, typer.Argument(help="Feature tag to archive")],
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Preview planned changes")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    no_hints: Annotated[
        bool, typer.Option("--no-hints", help="Suppress next-step advisory hints")
    ] = False,
    target: TargetOption = None,
) -> None:
    """Archive all documents for a feature tag."""
    apply_target(target)
    from vaultspec_core.console import get_console

    console = get_console()
    from vaultspec_core.core.exceptions import VaultSpecError
    from vaultspec_core.core.types import get_context as _get_ctx
    from vaultspec_core.vaultcore.query import archive_feature

    try:
        result = archive_feature(_get_ctx().target_dir, feature_tag, dry_run=dry_run)
    except (VaultSpecError, OSError) as exc:
        _handle_error(exc, json_output=json_output)
        return
    if not dry_run and result["archived_count"] > 0:
        from vaultspec_core.cli._cache_hook import invalidate_graph_cache

        invalidate_graph_cache(_get_ctx().target_dir)
    outcome = (
        "updated" if (result["archived_count"] > 0 and not dry_run) else "unchanged"
    )
    from vaultspec_core.cli.rendering import emit_next_step_hint

    hint_dict = emit_next_step_hint(
        command="vault.feature.archive",
        outcome=outcome,
        json_output=json_output,
        no_hints=no_hints,
    )

    if json_output:
        import json

        from vaultspec_core.cli.rendering import json_envelope

        archive_status = (
            "removed" if result["archived_count"] and not dry_run else "unchanged"
        )
        typer.echo(
            json.dumps(
                json_envelope(
                    "vault.feature.archive",
                    archive_status,
                    result,
                    hints=hint_dict,
                ),
                indent=2,
                default=str,
            )
        )
        raise typer.Exit(0)

    if dry_run:
        console.print(
            f"[yellow]Dry-run: Previewing feature archive for '{feature_tag}'[/yellow]"
        )
        if result["paths"]:
            console.print("[yellow]Planned movements:[/yellow]")
            for p in result["paths"]:
                console.print(f"  {p}")
        else:
            console.print("[dim]No planned movements.[/dim]")

        if result.get("cross_links"):
            console.print(
                "[yellow]Warning: The following external documents link to "
                "feature documents and may become dangling:[/yellow]"
            )
            for link in result["cross_links"]:
                console.print(f"  {link['source_path']} -> {link['target']}")
        else:
            console.print("[green]No incoming cross-feature links found.[/green]")
    else:
        if result["archived_count"] == 0:
            console.print(f"[dim]No documents found for feature '{feature_tag}'.[/dim]")
        else:
            console.print(
                f"[green]Archived {result['archived_count']} documents.[/green]"
            )
            for p in result["paths"]:
                console.print(f"  {p}")


# ---- vault feature unarchive -------------------------------------------------


@feature_app.command("unarchive")
def cmd_feature_unarchive(
    feature_tag: Annotated[str, typer.Argument(help="Feature tag to unarchive")],
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Preview planned changes")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Restore all archived documents for a feature tag."""
    apply_target(target)
    from vaultspec_core.console import get_console
    from vaultspec_core.core.exceptions import VaultSpecError
    from vaultspec_core.core.types import get_context as _get_ctx
    from vaultspec_core.vaultcore.query import unarchive_feature

    try:
        result = unarchive_feature(_get_ctx().target_dir, feature_tag, dry_run=dry_run)
    except (VaultSpecError, OSError) as exc:
        _handle_error(exc, json_output=json_output)
        return
    if not dry_run and result["unarchived_count"] > 0:
        from vaultspec_core.cli._cache_hook import invalidate_graph_cache

        invalidate_graph_cache(_get_ctx().target_dir)
    console = get_console()
    if json_output:
        import json

        from vaultspec_core.cli.rendering import json_envelope

        unarchive_status = (
            "restored" if result["unarchived_count"] and not dry_run else "unchanged"
        )
        typer.echo(
            json.dumps(
                json_envelope("vault.feature.unarchive", unarchive_status, result),
                indent=2,
                default=str,
            )
        )
        raise typer.Exit(0)

    if dry_run:
        console.print(
            "[yellow]Dry-run: Previewing feature unarchive for "
            f"'{feature_tag}'[/yellow]"
        )
        if result["paths"]:
            console.print("[yellow]Planned restorations:[/yellow]")
            for p in result["paths"]:
                console.print(f"  {p}")
        else:
            console.print("[dim]No planned restorations.[/dim]")
    else:
        if result["unarchived_count"] == 0:
            console.print(
                f"[dim]No archived documents found for feature '{feature_tag}'.[/dim]"
            )
        else:
            console.print(
                f"[green]Unarchived {result['unarchived_count']} documents.[/green]"
            )
            for p in result["paths"]:
                console.print(f"  {p}")


# ---- vault feature rename ----------------------------------------------------


@feature_app.command("rename")
def cmd_feature_rename(
    old_feature: Annotated[str, typer.Argument(help="Current feature tag to rename")],
    new_feature: Annotated[str, typer.Argument(help="New feature tag name")],
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Preview planned changes without writing")
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help=(
                "Merge source into an existing target feature "
                "(per-file path collisions still refuse)"
            ),
        ),
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    no_hints: Annotated[
        bool, typer.Option("--no-hints", help="Suppress next-step advisory hints")
    ] = False,
    target: TargetOption = None,
) -> None:
    """Atomically rename a feature tag across every vault surface.

    Rewrites document filenames, the exec folder and exec record filenames,
    the #feature frontmatter tag, related: wiki-links, and the regenerated
    feature index.  Free-form body prose is never changed.

    A reverse journal is kept during the apply phase; any mid-apply failure
    rolls back all changes, leaving the vault byte-identical to its pre-rename
    state.  Use --force to merge the source feature into an existing target
    feature (per-file path collisions still refuse).
    """
    apply_target(target)
    from vaultspec_core.console import get_console
    from vaultspec_core.core.exceptions import VaultSpecError
    from vaultspec_core.core.types import get_context as _get_ctx
    from vaultspec_core.vaultcore.query import rename_feature

    console = get_console()

    try:
        result = rename_feature(
            _get_ctx().target_dir,
            old_feature,
            new_feature,
            dry_run=dry_run,
            force=force,
        )
    except (VaultSpecError, OSError) as exc:
        _handle_error(exc, json_output=json_output)
        return

    if not dry_run and result["renamed_count"] > 0:
        from vaultspec_core.cli._cache_hook import invalidate_graph_cache

        invalidate_graph_cache(_get_ctx().target_dir)

    outcome = (
        "updated" if (result["renamed_count"] > 0 and not dry_run) else "unchanged"
    )

    from vaultspec_core.cli.rendering import emit_next_step_hint

    hint_dict = emit_next_step_hint(
        command="vault.feature.rename",
        outcome=outcome,
        json_output=json_output,
        no_hints=no_hints,
    )

    if json_output:
        import json

        from vaultspec_core.cli.rendering import json_envelope

        rename_status = (
            "updated" if (result["renamed_count"] > 0 and not dry_run) else "unchanged"
        )
        typer.echo(
            json.dumps(
                json_envelope(
                    "vault.feature.rename",
                    rename_status,
                    result,
                    hints=hint_dict,
                ),
                indent=2,
                default=str,
            )
        )
        raise typer.Exit(0)

    if dry_run:
        console.print(
            f"[yellow]Dry-run: Previewing feature rename "
            f"'{old_feature}' -> '{new_feature}'[/yellow]"
        )
        if result["paths"]:
            n = result["renamed_count"]
            console.print(f"[yellow]Planned renames ({n} documents):[/yellow]")
            for p in result["paths"]:
                console.print(f"  {p['old']}  ->  {p['new']}")
        else:
            console.print("[dim]No documents found for this feature.[/dim]")

        if result.get("exec_folders"):
            console.print("[yellow]Exec folder renames:[/yellow]")
            for ef in result["exec_folders"]:
                console.print(f"  {ef['old']}  ->  {ef['new']}")

        tag_count = result.get("tag_rewrites", 0)
        rel_count = result.get("related_rewrites", 0)
        console.print(
            f"[dim]Predicted: {tag_count} tag rewrite(s), "
            f"{rel_count} related-link rewrite(s)[/dim]"
        )

        if result.get("cross_links"):
            console.print(
                "[yellow]Cross-feature incoming links (will be rewritten):[/yellow]"
            )
            for link in result["cross_links"]:
                console.print(f"  {link['source_path']} -> {link['target']}")
        else:
            console.print("[green]No incoming cross-feature links found.[/green]")
    else:
        if result["renamed_count"] == 0:
            console.print(f"[dim]No documents found for feature '{old_feature}'.[/dim]")
        else:
            console.print(
                f"[green]Renamed {result['renamed_count']} documents "
                f"'{old_feature}' -> '{new_feature}'.[/green]"
            )
            for p in result["paths"]:
                console.print(f"  {p['old']}  ->  {p['new']}")

            if result.get("exec_folders"):
                console.print("[green]Exec folder renamed:[/green]")
                for ef in result["exec_folders"]:
                    console.print(f"  {ef['old']}  ->  {ef['new']}")

            tag_count = result.get("tag_rewrites", 0)
            rel_count = result.get("related_rewrites", 0)
            console.print(
                f"[dim]{tag_count} tag rewrite(s), "
                f"{rel_count} cross-feature related-link rewrite(s)[/dim]"
            )


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
