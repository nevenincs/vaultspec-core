"""Pure helper functions backing the vault graph build and analysis passes.

Node-content helpers (:func:`extract_title`, :func:`extract_feature`,
:func:`edge_kind`, :func:`docnode_from_attrs`) and graph algorithms
(:func:`top_n`, :func:`betweenness_centrality`, :func:`pagerank`) used by
:class:`~vaultspec_core.graph.api.VaultGraph` during construction and
:meth:`~vaultspec_core.graph.api.VaultGraph.metrics`.  None of these touch the
filesystem; they operate on already-parsed content, tag sets, or an
in-memory ``networkx.DiGraph``.
"""

from __future__ import annotations

import logging
from typing import Any

import networkx as nx

from ..vaultcore import DocType
from .models import DocNode

logger = logging.getLogger(__name__)

__all__ = [
    "PAGERANK_ALPHA",
    "betweenness_centrality",
    "docnode_from_attrs",
    "edge_kind",
    "extract_feature",
    "extract_title",
    "pagerank",
    "top_n",
]

# PageRank damping factor.  Pinned so node-size hints are reproducible across
# builds and exactly testable; matches the networkx default of 0.85.
PAGERANK_ALPHA = 0.85


def extract_title(body: str) -> str | None:
    """Return the text of the first ``# ...`` heading, or ``None``."""
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return None


def extract_feature(tags: set[str]) -> str | None:
    """Return the feature name (no ``#``) from a document's tags.

    The feature is the lexicographically smallest non-directory tag.  Sorting
    makes the choice deterministic when a document carries more than one
    non-directory tag; iterating the raw ``set`` would otherwise pick an
    order-dependent tag under hash randomisation, which would make feature
    assignment - and therefore the derived relatedness edges that depend on
    it - non-reproducible across processes.

    Args:
        tags: The document's full tag set.

    Returns:
        The feature name without its ``#`` prefix, or ``None`` when the
        document carries no non-directory tag.
    """
    for tag in sorted(tags):
        if not DocType.from_tag(tag):
            return tag.lstrip("#")
    return None


def top_n(
    scores: dict[str, float],
    n: int = 10,
) -> dict[str, float]:
    """Return the top *n* entries from *scores* by value descending."""
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return dict(ranked[:n])


def betweenness_centrality(g: nx.DiGraph[str]) -> dict[str, float]:
    """Compute betweenness centrality via the C-backed engine when available.

    Betweenness is the one O(V*E) algorithm on the opt-in analysis surface;
    ``rustworkx`` runs the same Brandes algorithm with the same
    normalisation orders of magnitude faster than pure-Python networkx.
    The networkx implementation remains the automatic fallback when the
    binary wheel is unavailable, so no platform loses the surface.

    Args:
        g: The (sub)graph to analyse.

    Returns:
        Mapping of node name to normalised betweenness score, matching
        ``nx.betweenness_centrality``'s semantics.
    """
    try:
        import rustworkx as rx
    except ImportError:  # pragma: no cover - wheel unavailable on platform
        return nx.betweenness_centrality(g)
    rgraph = rx.networkx_converter(g)
    scores = rx.betweenness_centrality(rgraph, normalized=True, endpoints=False)
    return {rgraph[index]: score for index, score in scores.items()}


def pagerank(
    g: nx.DiGraph[str],
    *,
    alpha: float = 0.85,
    max_iter: int = 100,
    tol: float = 1.0e-6,
) -> dict[str, float]:
    """Compute PageRank with a deterministic pure-Python power iteration.

    networkx 3.6 routes :func:`networkx.pagerank` through a SciPy sparse
    solver, and this project ships neither NumPy nor SciPy.  This helper
    reproduces the classic power-iteration PageRank in pure Python so node
    sizing stays a zero-dependency, fully deterministic computation that
    mirrors the networkx default semantics: a uniform initial vector, uniform
    redistribution of dangling-node mass, edge-``weight`` biasing, the same
    damping factor, and the same node-count-scaled L1 convergence test
    (``err < n * tol``).  Nodes are iterated in sorted key order so the
    floating-point reduction order - and therefore every score down to the
    last ulp - is independent of the order edges were inserted into the graph.
    On the rare non-converging graph it falls back to the last iterate (after
    logging a warning) rather than raising, so a graph build can never crash on
    node sizing.

    Args:
        g: The directed graph to rank.  Edge ``weight`` attributes, when
            present, bias the rank distribution.
        alpha: Damping factor (teleport probability is ``1 - alpha``).
        max_iter: Maximum power-iteration steps.
        tol: Per-node L1 convergence tolerance; the aggregate threshold is
            ``n * tol``, matching networkx.

    Returns:
        Mapping of node key to PageRank score; scores sum to ``1.0``.  An
        empty graph yields an empty mapping.
    """
    # Iterate nodes in sorted key order rather than insertion order.  The L1
    # error and per-node sums are accumulated as floating-point reductions, so
    # the summation order affects the last ulp of every score; pinning the
    # order to the sorted keys makes the result bit-identical regardless of the
    # order edges were inserted (the regression guard in test_pagerank).
    nodes: list[str] = sorted(g.nodes())
    n = len(nodes)
    if n == 0:
        return {}

    rank: dict[str, float] = dict.fromkeys(nodes, 1.0 / n)
    teleport = (1.0 - alpha) / n

    # Pre-compute weighted out-degree so dangling nodes are detected once.
    out_weight: dict[str, float] = {}
    for node in nodes:
        total = 0.0
        for _, _, data in g.out_edges(node, data=True):
            total += float(data.get("weight", 1.0))
        out_weight[node] = total

    err = 0.0
    for _ in range(max_iter):
        prev = rank
        # Dangling mass: nodes with no out-edges spread their rank uniformly.
        dangling_mass = alpha * sum(
            prev[node] for node in nodes if out_weight[node] == 0.0
        )
        nxt: dict[str, float] = dict.fromkeys(nodes, teleport + dangling_mass / n)
        for node in nodes:
            if out_weight[node] == 0.0:
                continue
            share = alpha * prev[node] / out_weight[node]
            for _, target, data in g.out_edges(node, data=True):
                nxt[target] += share * float(data.get("weight", 1.0))
        err = sum(abs(nxt[node] - prev[node]) for node in nodes)
        rank = nxt
        # networkx scales the tolerance by the node count.
        if err < n * tol:
            return rank

    logger.warning(
        "PageRank did not converge in %d iterations (final L1 error %.3e >= %.3e); "
        "returning the last iterate",
        max_iter,
        err,
        n * tol,
    )
    return rank


def docnode_from_attrs(name: str, attrs: dict[str, Any]) -> DocNode:
    """Reconstruct a :class:`DocNode` from cached networkx node attributes.

    Inverts :meth:`DocNode.to_nx_attrs`: the stored ``path`` string becomes a
    :class:`pathlib.Path` (or ``None`` for phantoms), the ``doc_type`` value
    string becomes a :class:`~vaultspec_core.vaultcore.DocType`, and the sorted
    ``tags``, ``out_links``, and ``in_links`` lists become sets.  The ``body``
    attribute is not part of ``to_nx_attrs`` and is restored separately by the
    cache loader.

    Args:
        name: The node key (used as the :class:`DocNode` ``name``).
        attrs: The networkx node attribute dict from the cached node-link data.

    Returns:
        A :class:`DocNode` equivalent to the one a fresh build would produce
        for this node, minus its body text.
    """
    import pathlib

    raw_path = attrs.get("path")
    doc_type_value = attrs.get("doc_type")
    return DocNode(
        path=pathlib.Path(raw_path) if raw_path else None,
        name=attrs.get("name", name),
        doc_type=DocType(doc_type_value) if doc_type_value else None,
        feature=attrs.get("feature"),
        date=attrs.get("date"),
        modified=attrs.get("modified"),
        title=attrs.get("title"),
        tags=set(attrs.get("tags", [])),
        frontmatter=attrs.get("frontmatter", {}),
        word_count=attrs.get("word_count", 0),
        out_links=set(attrs.get("out_links", [])),
        in_links=set(attrs.get("in_links", [])),
        phantom=attrs.get("phantom", False),
    )


def edge_kind(provenance: set[str]) -> str:
    """Map a set of provenance sources to a single edge ``kind`` value.

    Args:
        provenance: The provenance tokens recorded for an edge during build.
            Each token is one of ``"body"`` (a body wiki-link) or
            ``"related"`` (a ``related:`` frontmatter entry).

    Returns:
        ``"both"`` when the target is reached by both a body wiki-link and a
        ``related:`` entry, otherwise the single source token (``"body"`` or
        ``"related"``).
    """
    if "body" in provenance and "related" in provenance:
        return "both"
    if "related" in provenance:
        return "related"
    return "body"
