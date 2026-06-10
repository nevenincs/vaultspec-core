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

from vaultspec_core.cli._target import TargetOption, apply_target

__all__ = ["link_app"]

link_app = typer.Typer(
    help="Inspect and mutate vault document edges via related: frontmatter.",
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
