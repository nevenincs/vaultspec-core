"""Box-free tree and ASCII topology rendering for the vault graph.

Backs :meth:`~vaultspec_core.graph.api.VaultGraph.render_ascii`,
:meth:`~vaultspec_core.graph.api.VaultGraph.render_tree_lines`, and
:meth:`~vaultspec_core.graph.api.VaultGraph.render_tree`, which delegate here
as thin wrappers.  ``phart`` renders the actual graph topology as ASCII;
:func:`render_tree_lines` builds the complementary box-free hierarchical tree
grouped by feature and doc-type via
:func:`~vaultspec_core.cli.rendering.render_tree`'s plain-text vocabulary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vaultspec_core.cli.rendering import TreeLine

    from .api import VaultGraph
    from .models import DocNode

#: Maximum lines the tree render prints.  The title always carries the
#: full corpus counts, the truncation is explicitly marked, and the
#: ``--json`` envelope remains the uncapped machine contract, per the
#: report-volume policy.
TREE_RENDER_CAP = 1000


def render_ascii(
    graph: VaultGraph,
    feature: str | None = None,
) -> str:
    """Render the graph as an ASCII diagram via ``phart``.

    Uses ``phart.ASCIIRenderer`` to produce a native directed-graph
    layout with box-drawn nodes and edge arrows  - the actual graph
    topology, not a hierarchical tree.

    Args:
        graph: The vault graph to render.
        feature: When set, render only that feature's subgraph.

    Returns:
        Multi-line ASCII string of the graph layout.
    """
    from phart import ASCIIRenderer

    g = graph.subgraph(feature=feature)
    renderer = ASCIIRenderer(g)
    return renderer.render()


def render_tree_lines(
    graph: VaultGraph,
    feature: str | None = None,
) -> list[TreeLine]:
    """Build a box-free :class:`~vaultspec_core.cli.rendering.TreeLine` list.

    Renders the vault as a hierarchical tree grouped by feature and
    doc-type, using the plain-text shape vocabulary.  This is
    complementary to :func:`render_ascii` which shows the actual graph
    topology.

    Args:
        graph: The vault graph to render.
        feature: Optional feature name to scope the tree.

    Returns:
        A list of :class:`~vaultspec_core.cli.rendering.TreeLine` objects
        ready for :func:`~vaultspec_core.cli.rendering.render_tree`.
    """
    from vaultspec_core.cli.rendering import TreeLine

    lines: list[TreeLine] = []

    if feature:
        nodes = graph.get_feature_nodes(feature)
        lines.extend(_build_typed_node_lines(graph, nodes, depth=0))
        return lines

    for feat in graph.get_features():
        feat_nodes = graph.get_feature_nodes(feat)
        lines.append(
            TreeLine(
                f"#{feat}  {len(feat_nodes)} docs",
                depth=0,
                style="bold cyan",
            )
        )
        lines.extend(_build_typed_node_lines(graph, feat_nodes, depth=1))

    untagged = [n for n in graph.nodes.values() if not n.feature and not n.phantom]
    if untagged:
        lines.append(
            TreeLine(
                f"(untagged)  {len(untagged)} docs",
                depth=0,
                style="bold yellow",
            )
        )
        lines.extend(
            _build_typed_node_lines(
                graph, sorted(untagged, key=lambda n: n.name), depth=1
            )
        )

    return lines


def render_tree(
    graph: VaultGraph,
    feature: str | None = None,
) -> None:
    """Print a box-free hierarchical tree to the console.

    Renders the vault grouped by feature and doc-type via the plain-text
    shape vocabulary.  This is complementary to :func:`render_ascii` which
    shows the actual graph topology.  At most :data:`TREE_RENDER_CAP`
    lines are printed; a marked truncation line reports the remainder and
    points at feature scoping or ``--json``.

    Args:
        graph: The vault graph to render.
        feature: Optional feature name to scope the tree.
    """
    from vaultspec_core.cli.rendering import TreeLine
    from vaultspec_core.cli.rendering import render_tree as _render_tree

    if feature:
        c = graph.counts(feature=feature)
        title = f"#{feature}  {c.docs} docs, {c.links} links"
    else:
        c = graph.counts()
        title = f".vault  {c.docs} docs, {c.links} links, {c.features} features"

    lines = render_tree_lines(graph, feature=feature)
    if len(lines) > TREE_RENDER_CAP:
        remainder = len(lines) - TREE_RENDER_CAP
        lines = [
            *lines[:TREE_RENDER_CAP],
            TreeLine(
                f"... {remainder} more lines truncated; scope with "
                "--feature <name> or use --json for the full graph",
                depth=0,
                style="dim",
            ),
        ]
    _render_tree(lines, title=title)


def _build_typed_node_lines(
    graph: VaultGraph,
    nodes: list[DocNode],
    depth: int,
) -> list[TreeLine]:
    """Build :class:`~vaultspec_core.cli.rendering.TreeLine` rows for *nodes*.

    Groups *nodes* by doc_type and emits one sub-heading per type
    followed by per-node rows and their out-link annotations.

    Args:
        graph: The vault graph *nodes* belong to (used to resolve out-link
            targets to their node metadata).
        nodes: The nodes to render.
        depth: Nesting depth of the type sub-heading rows (node rows are
            one level deeper, link rows two levels deeper).

    Returns:
        A flat list of :class:`~vaultspec_core.cli.rendering.TreeLine`
        entries in pre-order.
    """
    from vaultspec_core.cli.rendering import TreeLine

    lines: list[TreeLine] = []
    by_type: dict[str, list[DocNode]] = {}
    for node in nodes:
        key = node.doc_type.value if node.doc_type else "unknown"
        by_type.setdefault(key, []).append(node)

    for type_name in sorted(by_type):
        type_nodes = by_type[type_name]
        lines.append(
            TreeLine(
                f"{type_name}  ({len(type_nodes)})",
                depth=depth,
                style="bold",
            )
        )
        for node in type_nodes:
            label = _node_label_plain(node)
            lines.append(TreeLine(label, depth=depth + 1))

            for target in sorted(node.out_links):
                target_node = graph.nodes.get(target)
                if target_node and target_node.phantom:
                    lines.append(
                        TreeLine(
                            f"-> {target}  (not created)",
                            depth=depth + 2,
                            style="yellow",
                        )
                    )
                elif target_node:
                    dt_val = target_node.doc_type.value if target_node.doc_type else "?"
                    lines.append(
                        TreeLine(
                            f"-> {target}  {dt_val}",
                            depth=depth + 2,
                            style="dim",
                        )
                    )
                else:
                    lines.append(
                        TreeLine(
                            f"-> {target} (dangling)",
                            depth=depth + 2,
                            style="red",
                        )
                    )

    return lines


def _node_label_plain(node: DocNode) -> str:
    """Format a single-line plain-text label for a node.

    Returns a space-separated string with the node name, optional title,
    optional date, and a parenthetical of word-count and link counts.
    No Rich markup sequences are included.

    Args:
        node: The node to label.

    Returns:
        A human-readable single-line label string.
    """
    parts = [node.name]
    if node.title:
        parts.append(node.title)
    if node.date:
        parts.append(node.date)
    meta = []
    if node.word_count:
        meta.append(f"{node.word_count}w")
    meta.append(f"{len(node.in_links)}in")
    meta.append(f"{len(node.out_links)}out")
    parts.append(f"({', '.join(meta)})")
    return "  ".join(parts)
