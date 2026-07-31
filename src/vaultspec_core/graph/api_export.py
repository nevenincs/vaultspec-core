"""JSON serialisation of the vault document graph.

Sibling of :mod:`vaultspec_core.graph.api` (which owns
:class:`~vaultspec_core.graph.api.VaultGraph` itself) and
:mod:`vaultspec_core.graph.rendering` (the ASCII and tree views). This
module owns the wire format: the ``networkx`` node/edge structure enriched
with vault metrics, derived relatedness edges, and build-mode-independent
node paths.

The public surface stays on
:class:`~vaultspec_core.graph.api.VaultGraph` - call
``graph.to_dict()``/``graph.to_json()``, not these functions directly.
"""

from __future__ import annotations

import json
import pathlib
from typing import TYPE_CHECKING, Any

from networkx.readwrite import json_graph

from .derived import compute_derived_edges

if TYPE_CHECKING:
    from .api import VaultGraph

__all__ = ["relativise_node_path", "to_dict", "to_json"]


def relativise_node_path(root_dir: pathlib.Path, raw_path: Any) -> str | None:
    """Return *raw_path* as a vault-relative POSIX path, or ``None``.

    A working-tree node carries an absolute filesystem path; this rewrites
    it to the same vault-relative virtual form a ref-scoped node already
    uses (e.g. ``.vault/adr/foo.md``), so the serialised ``path`` field is
    consistent across build modes and never leaks an absolute OS path. A
    ``None`` path (phantom) stays ``None``; a path already relative or not
    under the root is returned unchanged (as POSIX).

    Args:
        root_dir: The vault root the path is made relative to.
        raw_path: The ``path`` value off a serialised node dict.

    Returns:
        The vault-relative POSIX path string, or ``None``.
    """
    if not raw_path:
        return None
    candidate = pathlib.PurePath(str(raw_path))
    root = pathlib.PurePath(str(root_dir))
    if candidate.is_absolute() and candidate.is_relative_to(root):
        return candidate.relative_to(root).as_posix()
    return candidate.as_posix()


def to_dict(
    graph: VaultGraph,
    feature: str | None = None,
    include_body: bool = False,
    *,
    node: str | None = None,
    depth: int = 1,
    include_derived: bool = True,
) -> dict[str, Any]:
    """Return *graph* as a JSON-serialisable dictionary.

    Uses ``networkx.readwrite.json_graph.node_link_data`` for the core
    node/edge structure, enriched with vault-specific metrics, the
    node-size hints carried on each node (``pagerank``, ``in_degree``), the
    explicit-edge attributes carried on each edge (``kind``,
    ``multiplicity``, ``weight``), and a parallel ``derived_edges`` array of
    implicit relatedness edges that is never mixed into the canonical
    ``edges`` array.

    Scoping precedence: when *node* is given the export is the ego subgraph
    around it at *depth* hops; otherwise *feature* scopes to a single
    feature; otherwise the full graph is exported.

    Args:
        graph: The graph being exported.
        feature: When set (and *node* is unset), export only that feature's
            subgraph.
        include_body: Include the full markdown body text in each node.
            Defaults to ``False`` to keep output compact.
        node: When set, export the ego subgraph around this node key.
        depth: Ego-graph radius in hops; only used when *node* is set.
        include_derived: When ``True`` (default), emit the ``derived_edges``
            array; when ``False`` emit an empty one.

    Returns:
        Dictionary with ``directed``, ``multigraph``, ``graph``, ``nodes``,
        ``edges``, ``derived_edges``, ``root``, ``ref``, ``feature``, and
        ``metrics`` keys. ``ref`` names the git ref for a ref-scoped build
        (issue #160) and is ``None`` for a working-tree build.
    """
    if node is not None:
        g = graph.ego_subgraph(node, depth=depth)
    else:
        g = graph.subgraph(feature=feature)

    # networkx native serialisation - pass edges="edges" explicitly so the
    # wire key is deterministic regardless of networkx version. networkx
    # changed the default from "links" (<=3.5) to "edges" (>=3.6).
    data = json_graph.node_link_data(g, edges="edges")

    # Strip body from nodes unless requested
    if not include_body:
        for node_dict in data.get("nodes", []):
            node_dict.pop("body", None)

    # Inject body when requested (body is not on the nx node)
    if include_body:
        for node_dict in data.get("nodes", []):
            nid = node_dict.get("id", "")
            doc = graph.nodes.get(nid)
            if doc:
                node_dict["body"] = doc.body

    # Normalise every node ``path`` to a vault-relative POSIX path so the wire
    # format never leaks an absolute OS path and is identical across build
    # modes (issue #160 consumer symmetry): a ref-scoped node already carries
    # its virtual tree path (e.g. ``.vault/adr/foo.md``), and a working-tree
    # node's absolute filesystem path is relativised to the same shape here.
    # Phantoms (``path is None``) and any path already outside the root are
    # left untouched.
    for node_dict in data.get("nodes", []):
        node_dict["path"] = relativise_node_path(graph.root_dir, node_dict.get("path"))

    # Derived (implicit) relatedness edges. Computed on demand and kept in a
    # SEPARATE array so checkers and the canonical edges list stay free of
    # synthetic edges. When the export is scoped (ego or feature), the derived
    # computation is scoped to the exported node set too, so an ego query pays
    # only its local pair cost instead of the whole-graph O(n^2) pass that is
    # then filtered away. An unscoped (full-graph) export passes scope=None
    # and computes over every pair.
    derived: list[dict[str, Any]] = []
    if include_derived:
        scope = None if (node is None and feature is None) else set(g.nodes())
        derived = [edge.to_dict() for edge in compute_derived_edges(graph, scope)]
    data["derived_edges"] = derived

    # Enrich with vault-specific metadata.
    # Pass the already-computed subgraph so betweenness_centrality runs exactly
    # once per to_dict call instead of recomputing via a second subgraph()
    # traversal inside metrics().
    m = graph.metrics(feature=feature, _g=g)
    data["root"] = str(graph.root_dir)
    # Ref-scoped builds (issue #160) name the snapshot here; a working-tree
    # build carries ``ref: null`` so the v2 envelope stays self-describing
    # without changing any node or edge shape.
    data["ref"] = graph.ref
    data["feature"] = feature
    data["metrics"] = m.to_dict()

    return data


def to_json(
    graph: VaultGraph,
    feature: str | None = None,
    include_body: bool = False,
    indent: int = 2,
) -> str:
    """Serialise *graph* to a JSON string.

    Args:
        graph: The graph being serialised.
        feature: Scope to a single feature.
        include_body: Include full markdown body in output.
        indent: JSON indentation level.

    Returns:
        JSON string.
    """
    return json.dumps(
        to_dict(graph, feature=feature, include_body=include_body),
        indent=indent,
        default=str,
    )
