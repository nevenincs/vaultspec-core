"""Vault feature-tag verbs  - list, index, archive, unarchive, and rename.

Registers the ``vaultspec-core vault feature ...`` subcommands (mounted on
:data:`vaultspec_core.cli.vault_cmd.feature_app`). Split out of
:mod:`vaultspec_core.cli.vault_cmd` to keep that module under the project's
line-count ceiling; all commands re-export through ``vault_cmd`` so no
import site outside the package changes. All backend logic lives in
:mod:`vaultspec_core.vaultcore.query` and :mod:`vaultspec_core.vaultcore.index`.

Each ``@feature_app.command`` closure below is a thin Typer-parsed shim: it
only exists to carry the CLI ``Annotated`` option metadata. The command body
lives in a module-level ``_run_feature_*`` function (plus small ``_emit_*``/
``_print_*`` helpers for the JSON envelope and text-rendering branches), kept
top-level rather than nested so it is scored, read, and tested on its own.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

import typer

from vaultspec_core.cli._errors import handle_error as _handle_error
from vaultspec_core.cli._target import TargetOption, apply_target

if TYPE_CHECKING:
    from pathlib import Path

    import typer as _typer

    from vaultspec_core.graph import VaultGraph
    from vaultspec_core.vaultcore.query import (
        FeatureArchiveResult,
        FeatureDetail,
        FeatureRenameResult,
        FeatureUnarchiveResult,
    )

__all__ = ["register_feature_commands"]


def _filter_stale_features(
    features: list[FeatureDetail], stale_days: int
) -> list[FeatureDetail]:
    """Return features whose latest activity is older than *stale_days*.

    A feature with no parseable ``latest_activity`` is treated as stale so
    a sweep surfaces it rather than silently hiding undated work. The
    comparison is anchored on today's date.
    """
    import datetime as _dt

    from vaultspec_core.vaultcore.models import parse_lenient_date, vault_today

    cutoff = vault_today() - _dt.timedelta(days=stale_days)
    stale: list[FeatureDetail] = []
    for feature in features:
        parsed = parse_lenient_date(feature.get("latest_activity"))
        if parsed is None or parsed < cutoff:
            stale.append(feature)
    return stale


def register_feature_commands(feature_app: _typer.Typer) -> None:
    """Register the ``vault feature ...`` verbs on *feature_app*.

    Args:
        feature_app: The ``vault feature`` command group to mount the verbs on.
    """
    _register_feature_list_commands(feature_app)
    _register_feature_archive_commands(feature_app)
    _register_feature_rename_command(feature_app)


# ---- vault feature list / index ---------------------------------------------


def _emit_feature_list_json(features: list[FeatureDetail]) -> None:
    """Print the ``vault feature list`` JSON envelope."""
    import json

    from vaultspec_core.cli.rendering import json_envelope

    typer.echo(
        json.dumps(
            json_envelope("vault.feature.list", "unchanged", {"features": features}),
            indent=2,
            default=str,
        )
    )


def _print_feature_list_row(f: FeatureDetail) -> None:
    """Print one feature's summary row for ``vault feature list``."""
    from vaultspec_core.console import get_console

    types_str = ", ".join(f["types"])
    plan_marker = " [green]plan[/green]" if f["has_plan"] else ""
    name = f["name"]
    count = f["doc_count"]
    latest = f.get("latest_activity")
    activity = f"  [dim]{latest}[/dim]" if latest else ""
    get_console().print(
        f"  [bold]{name}[/bold]  {count} docs  ({types_str}){plan_marker}{activity}"
    )


def _run_feature_list(
    date: str | None,
    orphaned: bool,
    type_filter: str | None,
    stale_days: int | None,
    json_output: bool,
    target: Path | None,
) -> None:
    """Body of ``vault feature list``."""
    apply_target(target)
    from vaultspec_core.console import get_console
    from vaultspec_core.core.types import get_context as _get_ctx
    from vaultspec_core.vaultcore.query import list_feature_details

    features = list_feature_details(
        _get_ctx().target_dir,
        date=date,
        doc_type=type_filter,
        orphaned_only=orphaned,
    )
    if stale_days is not None:
        features = _filter_stale_features(features, stale_days)

    if json_output:
        _emit_feature_list_json(features)
        raise typer.Exit(0)

    if not features:
        get_console().print("[dim]No features found.[/dim]")
        return
    for f in features:
        _print_feature_list_row(f)


def _emit_feature_index_json(status: str, generated_paths: list[Path]) -> None:
    """Print the ``vault feature index`` JSON envelope."""
    import json

    from vaultspec_core.cli.rendering import json_envelope

    typer.echo(
        json.dumps(
            json_envelope(
                "vault.feature.index",
                status,
                {"generated": [str(p) for p in generated_paths]},
            ),
            indent=2,
        )
    )


def _generate_feature_indexes(
    graph: VaultGraph,
    root_dir: Path,
    features: list[str],
    json_output: bool,
) -> list[Path]:
    """Regenerate the index document for each feature, returning written paths."""
    from vaultspec_core.console import get_console
    from vaultspec_core.vaultcore.index import generate_feature_index

    generated_paths: list[Path] = []
    for feat in features:
        nodes = graph.get_feature_nodes(feat)
        if not nodes:
            if not json_output:
                get_console().print(f"[dim]No documents found for #{feat}.[/dim]")
            continue
        path = generate_feature_index(root_dir, feat, nodes=nodes)
        generated_paths.append(path)
        if not json_output:
            get_console().print(f"[green]Index:[/green] {path}")
    return generated_paths


def _run_feature_index(
    feature: str | None,
    json_output: bool,
    target: Path | None,
) -> None:
    """Body of ``vault feature index``."""
    apply_target(target)
    from vaultspec_core.console import get_console
    from vaultspec_core.core.types import get_context as _get_ctx
    from vaultspec_core.graph import VaultGraph

    root_dir = _get_ctx().target_dir
    graph = VaultGraph(root_dir)
    features = [feature.lstrip("#")] if feature else graph.get_features()

    if not features:
        if json_output:
            _emit_feature_index_json("unchanged", [])
            raise typer.Exit(0)
        get_console().print("[dim]No features found in vault.[/dim]")
        return

    generated_paths = _generate_feature_indexes(graph, root_dir, features, json_output)

    if generated_paths:
        from vaultspec_core.cli._cache_hook import invalidate_graph_cache

        invalidate_graph_cache(root_dir)

    if json_output:
        index_status = "updated" if generated_paths else "unchanged"
        _emit_feature_index_json(index_status, generated_paths)
        raise typer.Exit(0)


def _register_feature_list_commands(feature_app: _typer.Typer) -> None:
    """Register the ``list`` and ``index`` verbs on *feature_app*.

    Args:
        feature_app: The ``vault feature`` command group to mount the verbs on.
    """

    @feature_app.command("list")
    def cmd_feature_list(  # pyright: ignore[reportUnusedFunction]
        date: Annotated[
            str | None, typer.Option("--date", help="Filter by date")
        ] = None,
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
        json_output: Annotated[
            bool, typer.Option("--json", help="Output as JSON")
        ] = False,
        target: TargetOption = None,
    ) -> None:
        """List all feature tags in the vault."""
        _run_feature_list(date, orphaned, type_filter, stale_days, json_output, target)

    # ---- vault feature index ---------------------------------------------

    @feature_app.command("index")
    def cmd_feature_index(  # pyright: ignore[reportUnusedFunction]
        feature: Annotated[
            str | None,
            typer.Option(
                "--feature", "-f", help="Generate index for a specific feature"
            ),
        ] = None,
        json_output: Annotated[
            bool, typer.Option("--json", help="Output as JSON")
        ] = False,
        target: TargetOption = None,
    ) -> None:
        """Generate or update feature index documents.

        Writes a ``<feature>.index.md`` into ``.vault/index/`` for each
        feature tag (or a specific one with ``--feature``). Each index links
        to all documents sharing that feature tag, making implicit feature
        clusters explicit in the graph.
        """
        _run_feature_index(feature, json_output, target)

    # ---- vault feature archive --------------------------------------------


# ---- vault feature archive / unarchive ---------------------------------------


def _emit_feature_archive_json(
    result: FeatureArchiveResult, hint_dict: dict[str, object] | None, *, dry_run: bool
) -> None:
    """Print the ``vault feature archive`` JSON envelope."""
    import json

    from vaultspec_core.cli.rendering import json_envelope

    archive_status = (
        "removed" if result["archived_count"] and not dry_run else "unchanged"
    )
    typer.echo(
        json.dumps(
            json_envelope(
                "vault.feature.archive", archive_status, result, hints=hint_dict
            ),
            indent=2,
            default=str,
        )
    )


def _print_feature_archive_dry_run(
    feature_tag: str, result: FeatureArchiveResult
) -> None:
    """Print the dry-run preview for ``vault feature archive``."""
    from vaultspec_core.console import get_console

    console = get_console()
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


def _print_feature_archive_result(
    feature_tag: str, result: FeatureArchiveResult
) -> None:
    """Print the applied-result summary for ``vault feature archive``."""
    from vaultspec_core.console import get_console

    console = get_console()
    if result["archived_count"] == 0:
        console.print(f"[dim]No documents found for feature '{feature_tag}'.[/dim]")
        return
    console.print(f"[green]Archived {result['archived_count']} documents.[/green]")
    for p in result["paths"]:
        console.print(f"  {p}")


def _run_feature_archive(
    feature_tag: str,
    dry_run: bool,
    json_output: bool,
    no_hints: bool,
    target: Path | None,
) -> None:
    """Body of ``vault feature archive``."""
    apply_target(target)
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
        _emit_feature_archive_json(result, hint_dict, dry_run=dry_run)
        raise typer.Exit(0)

    if dry_run:
        _print_feature_archive_dry_run(feature_tag, result)
    else:
        _print_feature_archive_result(feature_tag, result)


def _emit_feature_unarchive_json(
    result: FeatureUnarchiveResult, *, dry_run: bool
) -> None:
    """Print the ``vault feature unarchive`` JSON envelope."""
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


def _print_feature_unarchive_dry_run(
    feature_tag: str, result: FeatureUnarchiveResult
) -> None:
    """Print the dry-run preview for ``vault feature unarchive``."""
    from vaultspec_core.console import get_console

    console = get_console()
    console.print(
        f"[yellow]Dry-run: Previewing feature unarchive for '{feature_tag}'[/yellow]"
    )
    if result["paths"]:
        console.print("[yellow]Planned restorations:[/yellow]")
        for p in result["paths"]:
            console.print(f"  {p}")
    else:
        console.print("[dim]No planned restorations.[/dim]")


def _print_feature_unarchive_result(
    feature_tag: str, result: FeatureUnarchiveResult
) -> None:
    """Print the applied-result summary for ``vault feature unarchive``."""
    from vaultspec_core.console import get_console

    console = get_console()
    if result["unarchived_count"] == 0:
        console.print(
            f"[dim]No archived documents found for feature '{feature_tag}'.[/dim]"
        )
        return
    console.print(f"[green]Unarchived {result['unarchived_count']} documents.[/green]")
    for p in result["paths"]:
        console.print(f"  {p}")


def _run_feature_unarchive(
    feature_tag: str,
    dry_run: bool,
    json_output: bool,
    target: Path | None,
) -> None:
    """Body of ``vault feature unarchive``."""
    apply_target(target)
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

    if json_output:
        _emit_feature_unarchive_json(result, dry_run=dry_run)
        raise typer.Exit(0)

    if dry_run:
        _print_feature_unarchive_dry_run(feature_tag, result)
    else:
        _print_feature_unarchive_result(feature_tag, result)


def _register_feature_archive_commands(feature_app: _typer.Typer) -> None:
    """Register the ``archive`` and ``unarchive`` verbs on *feature_app*.

    Args:
        feature_app: The ``vault feature`` command group to mount the verbs on.
    """

    @feature_app.command("archive")
    def cmd_feature_archive(  # pyright: ignore[reportUnusedFunction]
        feature_tag: Annotated[str, typer.Argument(help="Feature tag to archive")],
        dry_run: Annotated[
            bool, typer.Option("--dry-run", help="Preview planned changes")
        ] = False,
        json_output: Annotated[
            bool, typer.Option("--json", help="Output as JSON")
        ] = False,
        no_hints: Annotated[
            bool, typer.Option("--no-hints", help="Suppress next-step advisory hints")
        ] = False,
        target: TargetOption = None,
    ) -> None:
        """Archive all documents for a feature tag."""
        _run_feature_archive(feature_tag, dry_run, json_output, no_hints, target)

    # ---- vault feature unarchive -------------------------------------------

    @feature_app.command("unarchive")
    def cmd_feature_unarchive(  # pyright: ignore[reportUnusedFunction]
        feature_tag: Annotated[str, typer.Argument(help="Feature tag to unarchive")],
        dry_run: Annotated[
            bool, typer.Option("--dry-run", help="Preview planned changes")
        ] = False,
        json_output: Annotated[
            bool, typer.Option("--json", help="Output as JSON")
        ] = False,
        target: TargetOption = None,
    ) -> None:
        """Restore all archived documents for a feature tag."""
        _run_feature_unarchive(feature_tag, dry_run, json_output, target)

    # ---- vault feature rename ----------------------------------------------


# ---- vault feature rename -----------------------------------------------------


def _emit_feature_rename_json(
    result: FeatureRenameResult, hint_dict: dict[str, object] | None, *, dry_run: bool
) -> None:
    """Print the ``vault feature rename`` JSON envelope."""
    import json

    from vaultspec_core.cli.rendering import json_envelope

    rename_status = (
        "updated" if (result["renamed_count"] > 0 and not dry_run) else "unchanged"
    )
    typer.echo(
        json.dumps(
            json_envelope(
                "vault.feature.rename", rename_status, result, hints=hint_dict
            ),
            indent=2,
            default=str,
        )
    )


def _print_feature_rename_dry_run(
    old_feature: str, new_feature: str, result: FeatureRenameResult
) -> None:
    """Print the dry-run preview for ``vault feature rename``."""
    from vaultspec_core.console import get_console

    console = get_console()
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


def _print_feature_rename_result(
    old_feature: str, new_feature: str, result: FeatureRenameResult
) -> None:
    """Print the applied-result summary for ``vault feature rename``."""
    from vaultspec_core.console import get_console

    console = get_console()
    if result["renamed_count"] == 0:
        console.print(f"[dim]No documents found for feature '{old_feature}'.[/dim]")
        return

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
        f"[dim]{tag_count} tag rewrite(s), {rel_count} related-link rewrite(s)[/dim]"
    )


def _run_feature_rename(
    old_feature: str,
    new_feature: str,
    dry_run: bool,
    force: bool,
    json_output: bool,
    no_hints: bool,
    target: Path | None,
) -> None:
    """Body of ``vault feature rename``."""
    apply_target(target)
    from vaultspec_core.core.exceptions import VaultSpecError
    from vaultspec_core.core.types import get_context as _get_ctx
    from vaultspec_core.vaultcore.query import rename_feature

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
        _emit_feature_rename_json(result, hint_dict, dry_run=dry_run)
        raise typer.Exit(0)

    if dry_run:
        _print_feature_rename_dry_run(old_feature, new_feature, result)
    else:
        _print_feature_rename_result(old_feature, new_feature, result)


def _register_feature_rename_command(feature_app: _typer.Typer) -> None:
    """Register the ``rename`` verb on *feature_app*.

    Args:
        feature_app: The ``vault feature`` command group to mount the verbs on.
    """

    @feature_app.command("rename")
    def cmd_feature_rename(  # pyright: ignore[reportUnusedFunction]
        old_feature: Annotated[
            str, typer.Argument(help="Current feature tag to rename")
        ],
        new_feature: Annotated[str, typer.Argument(help="New feature tag name")],
        dry_run: Annotated[
            bool,
            typer.Option("--dry-run", help="Preview planned changes without writing"),
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
        json_output: Annotated[
            bool, typer.Option("--json", help="Output as JSON")
        ] = False,
        no_hints: Annotated[
            bool, typer.Option("--no-hints", help="Suppress next-step advisory hints")
        ] = False,
        target: TargetOption = None,
    ) -> None:
        """Atomically rename a feature tag across every vault surface.

        Rewrites document filenames, the exec folder and exec record filenames,
        the #feature frontmatter tag, related: wiki-links, and the regenerated
        feature index.  Free-form body prose is never changed.

        A reverse journal is kept during the apply phase; if an error is raised
        while applying, the changes made so far are rolled back to the pre-rename
        state.  Use --force to merge the source feature into an existing target
        feature (per-file path collisions still refuse).
        """
        _run_feature_rename(
            old_feature, new_feature, dry_run, force, json_output, no_hints, target
        )
