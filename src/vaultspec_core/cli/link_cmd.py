"""Typer wiring for ``vaultspec-core vault link ...`` subcommand group.

Registers the three edge-CRUD verbs: ``list``, ``add``, and ``remove``.
All mutation touches only the ``related:`` frontmatter block via
:mod:`vaultspec_core.vaultcore.related_surgery`; body wiki-links are
never modified.  The subcommand group is mounted onto
:data:`vaultspec_core.cli.vault_cmd.vault_app` by :mod:`.vault_cmd`.

JSON envelopes:
    ``vaultspec.vault.link.list.v1``  - list verb output
    ``vaultspec.vault.link.add.v1``   - add verb output
    ``vaultspec.vault.link.remove.v1`` - remove verb output

Exit codes:
    0 - success or idempotent no-op
    1 - resolution failure, dangling refusal, or write error
"""

from __future__ import annotations

from typing import Annotated

import typer

from vaultspec_core.cli._app import make_app
from vaultspec_core.cli._target import TargetOption, apply_target

__all__ = ["link_app"]

link_app = make_app(
    help="Inspect and mutate vault document edges via related: frontmatter",
    no_args_is_help=True,
)


# ---------------------------------------------------------------------------
# vault link list
# ---------------------------------------------------------------------------


@link_app.command("list")
def cmd_link_list(
    src: Annotated[
        str | None,
        typer.Argument(
            help=(
                "Scope listing to edges from/to this document stem. "
                "Accepts stem, filename, path, or [[wiki-link]]."
            )
        ),
    ] = None,
    feature: Annotated[
        str | None,
        typer.Option(
            "--feature",
            "-f",
            help="Filter edges whose source has this feature tag",
        ),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """List related: edges in the vault document graph.

    When *src* is given the listing is scoped to that node's out-links
    (edges from *src* to others) and in-links (edges from others to *src*).
    Without *src* all edges in the graph are listed.  Use ``--feature`` to
    restrict to sources that carry the given feature tag.
    """
    apply_target(target)
    import json

    from vaultspec_core.cli.rendering import json_envelope
    from vaultspec_core.console import get_console
    from vaultspec_core.core.types import get_context as _get_ctx
    from vaultspec_core.graph import VaultGraph

    console = get_console()
    root_dir = _get_ctx().target_dir

    try:
        graph = VaultGraph(root_dir)
    except OSError as exc:
        if json_output:
            typer.echo(
                json.dumps(
                    json_envelope(
                        "vault.link.list",
                        "failed",
                        {"message": str(exc)},
                    ),
                    indent=2,
                )
            )
        else:
            console.print(f"[red]Error reading vault: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    # Resolve src argument to a stem
    src_stem: str | None = None
    if src is not None:
        from vaultspec_core.vaultcore.resolve import (
            RelatedResolutionError,
            resolve_related_inputs,
        )

        try:
            resolved = resolve_related_inputs([src], root_dir)
        except RelatedResolutionError:
            resolved = []

        if resolved:
            # resolved is like ["[[stem]]"]
            inner = resolved[0]
            src_stem = inner[2:-2] if inner.startswith("[[") else inner
        else:
            if json_output:
                typer.echo(
                    json.dumps(
                        json_envelope(
                            "vault.link.list",
                            "failed",
                            {"message": f"Cannot resolve source document: '{src}'"},
                        ),
                        indent=2,
                    )
                )
            else:
                console.print(f"[red]Cannot resolve source document: '{src}'[/red]")
            raise typer.Exit(code=1)

    feat = feature.lstrip("#") if feature else None

    # Build the edge list
    edges: list[dict[str, str]] = []

    if src_stem is not None:
        node = graph.nodes.get(src_stem)
        if node is None:
            if json_output:
                typer.echo(
                    json.dumps(
                        json_envelope(
                            "vault.link.list",
                            "failed",
                            {"message": f"Node not found: {src_stem}"},
                        ),
                        indent=2,
                    )
                )
            else:
                console.print(f"[red]Node not found: {src_stem}[/red]")
            raise typer.Exit(code=1)
        for tgt in sorted(node.out_links):
            edges.append({"src": src_stem, "dst": tgt, "direction": "out"})
        for lnk in sorted(node.in_links):
            edges.append({"src": lnk, "dst": src_stem, "direction": "in"})
    else:
        for name, node in sorted(graph.nodes.items()):
            if node.phantom:
                continue
            if feat and node.feature != feat:
                continue
            for tgt in sorted(node.out_links):
                edges.append({"src": name, "dst": tgt, "direction": "out"})

    if json_output:
        typer.echo(
            json.dumps(
                json_envelope(
                    "vault.link.list",
                    "unchanged",
                    {"edges": edges, "count": len(edges)},
                ),
                indent=2,
            )
        )
        return

    if not edges:
        console.print("[dim]No edges found.[/dim]")
        return

    for e in edges:
        direction_glyph = "->" if e["direction"] == "out" else "<-"
        console.print(f"  {e['src']}  {direction_glyph}  {e['dst']}")


# ---------------------------------------------------------------------------
# vault link add
# ---------------------------------------------------------------------------


@link_app.command("add")
def cmd_link_add(
    src: Annotated[
        str,
        typer.Argument(
            help=(
                "Source document to add the edge from. "
                "Accepts stem, filename, path, or [[wiki-link]]."
            )
        ),
    ],
    dst: Annotated[
        str,
        typer.Argument(
            help=(
                "Target document to link to. "
                "Accepts stem, filename, path, or [[wiki-link]]."
            )
        ),
    ],
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview the change without writing"),
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help=("Allow creating a dangling edge whose target is not a real document"),
        ),
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Add a related: edge from *src* to *dst*.

    Resolves both arguments to document stems.  Refuses to create a
    dangling edge (a target that resolves to no real document) unless
    ``--force`` is supplied.  Exits 0 when the edge was added or already
    exists; exits 1 on resolution failure or dangling refusal.
    """
    apply_target(target)

    from vaultspec_core.console import get_console
    from vaultspec_core.core.types import get_context as _get_ctx
    from vaultspec_core.graph import VaultGraph
    from vaultspec_core.vaultcore.related_surgery import append_related_entry
    from vaultspec_core.vaultcore.resolve import (
        RelatedResolutionError,
        resolve_related_inputs,
    )

    console = get_console()
    root_dir = _get_ctx().target_dir

    # Resolve src to an on-disk path
    try:
        src_links = resolve_related_inputs([src], root_dir)
    except RelatedResolutionError:
        src_links = []

    if not src_links:
        _emit_fail(
            json_output,
            console,
            "vault.link.add",
            f"Cannot resolve source document: '{src}'",
        )
        raise typer.Exit(code=1)

    src_stem = src_links[0][2:-2]  # strip [[ ]]

    # Resolve dst - may or may not exist (dangling check follows)
    try:
        dst_links = resolve_related_inputs([dst], root_dir)
        dst_stem = dst_links[0][2:-2]
        dangling = False
    except RelatedResolutionError:
        # Target does not resolve - may still be allowed with --force
        dst_stem = _normalise_stem(dst)
        dangling = True

    if dangling and not force:
        _emit_fail(
            json_output,
            console,
            "vault.link.add",
            (
                f"Target '{dst}' does not resolve to a real document. "
                "Use --force to create a dangling edge."
            ),
        )
        raise typer.Exit(code=1)

    # Find the source file path
    graph = VaultGraph(root_dir)
    src_node = graph.nodes.get(src_stem)
    if src_node is None or src_node.path is None:
        _emit_fail(
            json_output,
            console,
            "vault.link.add",
            f"Source node has no backing file: '{src_stem}'",
        )
        raise typer.Exit(code=1)

    # Idempotency check: edge already exists?
    if dst_stem in src_node.out_links:
        _emit_ok(
            json_output,
            console,
            "vault.link.add",
            "unchanged",
            src_stem,
            dst_stem,
            dry_run=False,
            message="edge already exists",
        )
        return

    if dry_run:
        _emit_ok(
            json_output,
            console,
            "vault.link.add",
            "created",
            src_stem,
            dst_stem,
            dry_run=True,
        )
        return

    try:
        added = append_related_entry(src_node.path, f"[[{dst_stem}]]")
    except Exception as exc:
        _emit_fail(
            json_output,
            console,
            "vault.link.add",
            f"Write failed: {exc}",
        )
        raise typer.Exit(code=1) from exc

    if added:
        from vaultspec_core.cli._cache_hook import invalidate_graph_cache

        invalidate_graph_cache(root_dir)

    status = "created" if added else "unchanged"
    _emit_ok(
        json_output,
        console,
        "vault.link.add",
        status,
        src_stem,
        dst_stem,
        dry_run=False,
    )


# ---------------------------------------------------------------------------
# vault link remove
# ---------------------------------------------------------------------------


@link_app.command("remove")
def cmd_link_remove(
    src: Annotated[
        str,
        typer.Argument(
            help=(
                "Source document to remove the edge from. "
                "Accepts stem, filename, path, or [[wiki-link]]."
            )
        ),
    ],
    dst: Annotated[
        str,
        typer.Argument(
            help=(
                "Target document to unlink. "
                "Accepts stem, filename, path, or [[wiki-link]]."
            )
        ),
    ],
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview the change without writing"),
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
    target: TargetOption = None,
) -> None:
    """Remove a related: edge from *src* to *dst*.

    Removing a non-existent edge is reported as unchanged (no-op), not an
    error.  Exits 0 on success or no-op; exits 1 on resolution failure or
    write error.
    """
    apply_target(target)

    from vaultspec_core.console import get_console
    from vaultspec_core.core.types import get_context as _get_ctx
    from vaultspec_core.graph import VaultGraph
    from vaultspec_core.vaultcore.related_surgery import remove_related_entries
    from vaultspec_core.vaultcore.resolve import (
        RelatedResolutionError,
        resolve_related_inputs,
    )

    console = get_console()
    root_dir = _get_ctx().target_dir

    # Resolve src
    try:
        src_links = resolve_related_inputs([src], root_dir)
    except RelatedResolutionError:
        src_links = []

    if not src_links:
        _emit_fail(
            json_output,
            console,
            "vault.link.remove",
            f"Cannot resolve source document: '{src}'",
        )
        raise typer.Exit(code=1)

    src_stem = src_links[0][2:-2]

    # Resolve dst (best-effort; fall back to normalised stem)
    try:
        dst_links = resolve_related_inputs([dst], root_dir)
        dst_stem = dst_links[0][2:-2]
    except RelatedResolutionError:
        dst_stem = _normalise_stem(dst)

    graph = VaultGraph(root_dir)
    src_node = graph.nodes.get(src_stem)
    if src_node is None or src_node.path is None:
        _emit_fail(
            json_output,
            console,
            "vault.link.remove",
            f"Source node has no backing file: '{src_stem}'",
        )
        raise typer.Exit(code=1)

    # No-op check: edge doesn't exist
    if dst_stem not in src_node.out_links:
        _emit_ok(
            json_output,
            console,
            "vault.link.remove",
            "unchanged",
            src_stem,
            dst_stem,
            dry_run=False,
            message="edge does not exist",
        )
        return

    if dry_run:
        _emit_ok(
            json_output,
            console,
            "vault.link.remove",
            "removed",
            src_stem,
            dst_stem,
            dry_run=True,
        )
        return

    try:
        removed = remove_related_entries(src_node.path, [dst_stem])
    except Exception as exc:
        _emit_fail(
            json_output,
            console,
            "vault.link.remove",
            f"Write failed: {exc}",
        )
        raise typer.Exit(code=1) from exc

    if removed:
        from vaultspec_core.cli._cache_hook import invalidate_graph_cache

        invalidate_graph_cache(root_dir)

    status = "removed" if removed else "unchanged"
    _emit_ok(
        json_output,
        console,
        "vault.link.remove",
        status,
        src_stem,
        dst_stem,
        dry_run=False,
    )


# ---------------------------------------------------------------------------
# Private rendering helpers shared by add / remove
# ---------------------------------------------------------------------------


def _normalise_stem(raw: str) -> str:
    """Return a best-effort stem from any user-supplied reference.

    Args:
        raw: User-supplied reference string (path, stem, wiki-link, etc.)

    Returns:
        A normalised lowercase stem string.
    """
    import pathlib

    s = raw.strip().strip("'\"")
    if s.startswith("[[") and s.endswith("]]"):
        s = s[2:-2].split("|")[0].strip()
    if s.endswith(".md"):
        s = s[:-3]
    return pathlib.Path(s).name.lower()


def _emit_fail(
    json_output: bool,
    console: object,
    command: str,
    message: str,
) -> None:
    """Emit a failure message to stdout (JSON) or console (text).

    Args:
        json_output: When ``True`` emit a JSON envelope; otherwise print
            a Rich-markup error line.
        console: Rich console instance for text output.
        command: Dotted command identifier for the JSON schema field.
        message: Human-readable failure description.
    """
    import json

    from rich.console import Console

    from vaultspec_core.cli.rendering import json_envelope

    if json_output:
        typer.echo(
            json.dumps(
                json_envelope(command, "failed", {"message": message}),
                indent=2,
            )
        )
    else:
        assert isinstance(console, Console)
        console.print(f"[red]{message}[/red]")


def _emit_ok(
    json_output: bool,
    console: object,
    command: str,
    status: str,
    src: str,
    dst: str,
    *,
    dry_run: bool,
    message: str = "",
) -> None:
    """Emit a success or no-op message.

    Args:
        json_output: When ``True`` emit a JSON envelope; otherwise print
            a human-readable line.
        console: Rich console instance.
        command: Dotted command identifier.
        status: Canonical outcome word (``created``, ``removed``,
            ``unchanged``).
        src: Source document stem.
        dst: Destination document stem.
        dry_run: When ``True`` append ``dry_run=True`` to the JSON payload.
        message: Optional detail annotation for the human-readable line.
    """
    import json

    from rich.console import Console

    from vaultspec_core.cli.rendering import json_envelope

    if json_output:
        payload: dict[str, object] = {"src": src, "dst": dst}
        if dry_run:
            payload["dry_run"] = True
        if message:
            payload["message"] = message
        typer.echo(
            json.dumps(
                json_envelope(command, status, payload),
                indent=2,
            )
        )
    else:
        assert isinstance(console, Console)
        detail = f"  ({message})" if message else ""
        prefix = "[dim]Would[/dim] " if dry_run else ""
        verb_map = {
            "created": "Added",
            "removed": "Removed",
            "unchanged": "Unchanged",
        }
        verb = verb_map.get(status, status.capitalize())
        console.print(f"{prefix}{verb}: {src} -> {dst}{detail}")
