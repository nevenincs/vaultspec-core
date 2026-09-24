"""Translate the canonical graph to and from its cached node-link form.

:mod:`~vaultspec_core.graph.cache` owns the cache *file* - its schema, its
fingerprint manifest, and the racily-clean validation that decides whether it
may be served. This module owns the other half: turning a built graph into the
node-link payload that file carries, and turning a validated payload back into
the pieces a :class:`~vaultspec_core.graph.api.VaultGraph` holds.

Both directions lived on ``VaultGraph`` until ``graph/api.py`` reached the
project's per-module line ceiling. They are a better fit here in any case: a
cached node carries attributes (``raw``, ``crlf``) that exist nowhere in a
freshly built graph, and keeping the code that adds them next to the code that
strips them back off is what stops the two drifting apart. The functions take
and return plain data rather than a graph, so this module does not import
``api`` and no cycle appears.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, NamedTuple, cast

from .algorithms import docnode_from_attrs
from .models import EncodingIssue
from .networkx_runtime import node_link_data, node_link_graph

if TYPE_CHECKING:
    import pathlib

    from . import cache
    from .models import DocNode
    from .networkx_runtime import NetworkXGraph

logger = logging.getLogger(__name__)

__all__ = ["RestoredGraph", "restore_graph", "to_cache_graph"]


class RestoredGraph(NamedTuple):
    """The graph state rebuilt from a validated cache payload.

    Attributes:
        digraph: The reconstructed networkx graph.
        nodes: Node key to :class:`~vaultspec_core.graph.models.DocNode`,
            each carrying its body.
        stem_index: Bare stem to the sorted node keys that share it, with
            phantoms excluded to match fresh-build semantics.
        raw_texts: Document path to ``(normalised text, source_had_crlf)``.
        dangling_links: The ``(source, target)`` pairs the cached build saw.
        encoding_issues: The read and decode failures it observed.
    """

    digraph: NetworkXGraph
    nodes: dict[str, DocNode]
    stem_index: dict[str, list[str]]
    raw_texts: dict[pathlib.Path, tuple[str, bool]]
    dangling_links: list[tuple[str, str]]
    encoding_issues: list[EncodingIssue]


def to_cache_graph(
    digraph: NetworkXGraph,
    nodes: dict[str, DocNode],
    raw_texts: dict[pathlib.Path, tuple[str, bool]],
) -> dict[str, Any]:
    """Serialise *digraph* to node-link form with each node's raw text attached.

    Uses the same ``edges="edges"`` contract the JSON export uses, then adds
    each node's raw document text and its CRLF flag.

    Raw rather than body text: the body is a prefix-strip away from it, while
    the raw text is not recoverable from the body at all. Storing the body
    left every cache hit re-reading the whole corpus for the text the check
    pipeline needs. The frontmatter this adds is 1.7 MB against 40.4 MB.

    Args:
        digraph: The built canonical graph.
        nodes: The graph's node map, for each node's body and path.
        raw_texts: The ingress read's per-document text map.

    Returns:
        A node-link ``dict`` with ``raw`` and ``crlf`` on each node.
    """
    data = node_link_data(digraph)
    for node_dict in data.get("nodes", []):
        nid = node_dict.get("id", "")
        doc = nodes.get(nid)
        raw, crlf = ("", False)
        if doc is not None and doc.path is not None:
            raw, crlf = raw_texts.get(doc.path, (doc.body, False))
        node_dict["raw"] = raw
        node_dict["crlf"] = crlf
    return data


def restore_graph(payload: cache.GraphCachePayload) -> RestoredGraph:
    """Rebuild the graph state from an already-validated cache *payload*.

    The result is behaviourally identical to a fresh build - same nodes,
    edges, attributes, node-size metrics and document text - and no filesystem
    read occurs. Restoring the raw-text map is what lets
    :meth:`~vaultspec_core.graph.api.VaultGraph.ensure_raw_texts` find its work
    already done after a cache hit.

    Each body is split back out of its raw text through the same
    :func:`~vaultspec_core.vaultcore.parser.split_frontmatter` the cold parse
    uses, so a cached body cannot drift from a parsed one.

    Args:
        payload: A payload that has passed
            :func:`vaultspec_core.graph.cache.validate`.

    Returns:
        The reconstructed :class:`RestoredGraph`.
    """
    import pathlib

    from ..vaultcore.parser import split_frontmatter

    digraph = node_link_graph(payload.graph)
    nodes: dict[str, DocNode] = {}
    raw_texts: dict[pathlib.Path, tuple[str, bool]] = {}
    by_stem: dict[str, list[str]] = {}

    for key in digraph.nodes():
        attrs = digraph.nodes[key]
        nodes[key] = docnode_from_attrs(key, attrs)
        # Raw text is held on the graph, body on the DocNode; neither is an nx
        # node attribute on a fresh build, so both are pulled back off the
        # cached attrs and dropped to keep the attribute set identical.
        raw = cast("str", attrs.pop("raw", ""))
        crlf = cast("bool", attrs.pop("crlf", False))
        node_path = nodes[key].path
        if node_path is not None:
            raw_texts[node_path] = (raw, crlf)
        nodes[key].body = split_frontmatter(raw).body if raw else ""
        # Phantoms are excluded from the stem index to match fresh-build
        # semantics: the file rebuild only indexes real nodes in passes 1a/1b;
        # phantoms are added later in pass 2 and never entered there.
        if not attrs.get("phantom", False):
            bare_stem = key.split("/", 1)[1] if "/" in key else key
            by_stem.setdefault(bare_stem, []).append(key)

    stem_index = {stem: sorted(keys) for stem, keys in by_stem.items()}
    # A document that failed to read or decode never becomes a usable node, so
    # the cache carries these separately; restoring them keeps a warm run's
    # encoding findings identical to a cold one's.
    encoding_issues = [
        EncodingIssue(pathlib.Path(raw_path), kind, detail, start)
        for raw_path, kind, detail, start in payload.encoding_issues
    ]
    logger.info(
        "Graph loaded from cache: %d nodes, %d edges",
        digraph.number_of_nodes(),
        digraph.number_of_edges(),
    )
    return RestoredGraph(
        digraph=digraph,
        nodes=nodes,
        stem_index=stem_index,
        raw_texts=raw_texts,
        dangling_links=[(pair[0], pair[1]) for pair in payload.dangling_links],
        encoding_issues=encoding_issues,
    )
