"""Derived relatedness edges computed over the canonical vault graph.

The canonical :class:`~vaultspec_core.graph.api.VaultGraph` DiGraph holds only
explicit, authored references (body wiki-links and ``related:`` frontmatter):
edge presence means "a real reference exists", which orphan, dangling, and
reference checkers rely on.  This module computes *implicit* relatedness
between documents - reciprocity, shared tags, and the networkx
link-prediction family - **without ever mutating that canonical graph**.  The
result is a parallel, on-demand edge set with explicit provenance so a GUI (and
the test suite) can always answer why two documents are considered related.

Each derived edge carries:

- ``kind``: the dominant provenance label among the contributing signals.
- ``signals``: a raw per-signal score map (every signal that fired).
- ``weight``: a composed score, a documented linear combination of the raw
  signals with version-pinned coefficients (the module-level ``COEFF_*``
  constants), so tests assert exact arithmetic.

All functions are pure and deterministic over a fixed graph: signal values and
the iteration order of the returned edge list depend only on the graph
contents, never on wall-clock or hash randomisation.

Exports:
    :class:`DerivedEdge`: One implicit relatedness edge with provenance.
    :func:`compute_derived_edges`: Build the full derived edge set for a graph.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import networkx as nx

from ..vaultcore import DocType

if TYPE_CHECKING:
    from .api import VaultGraph

__all__ = [
    "COEFFICIENTS_VERSION",
    "COEFF_ADAMIC_ADAR",
    "COEFF_CO_CITATION",
    "COEFF_JACCARD",
    "COEFF_RECIPROCITY",
    "COEFF_SHARED_FEATURE",
    "COEFF_SHARED_TAG",
    "DerivedEdge",
    "compute_derived_edges",
]

# ---------------------------------------------------------------------------
# Version-pinned composition coefficients
#
# The composed weight of a derived edge is a linear combination of its raw
# signal scores:
#
#     weight = COEFF_RECIPROCITY    * reciprocity
#            + COEFF_SHARED_FEATURE * shared_feature
#            + COEFF_SHARED_TAG     * shared_tag
#            + COEFF_JACCARD        * jaccard
#            + COEFF_ADAMIC_ADAR    * adamic_adar
#            + COEFF_CO_CITATION    * co_citation
#
# Only signals that fired contribute (absent signals are treated as 0.0).
# The coefficients are pinned and versioned so that a change to the blend is a
# deliberate, test-visible event.  ``adamic_adar`` is intentionally weighted
# below the unit signals because its raw value is unbounded above; the blend
# is a ranking aid, not a probability.
# ---------------------------------------------------------------------------

COEFFICIENTS_VERSION = 1

COEFF_RECIPROCITY = 1.0
COEFF_SHARED_FEATURE = 0.5
COEFF_SHARED_TAG = 0.25
COEFF_JACCARD = 1.0
COEFF_ADAMIC_ADAR = 0.1
COEFF_CO_CITATION = 0.3


@dataclass
class DerivedEdge:
    """One implicit relatedness edge between two canonical documents.

    Derived edges are undirected by nature (relatedness is symmetric), so
    ``source`` and ``target`` are emitted in sorted order to keep the edge
    set deterministic and free of mirrored duplicates.

    Attributes:
        source: First endpoint node key (lexicographically smaller).
        target: Second endpoint node key (lexicographically larger).
        kind: Dominant provenance label among the contributing signals.
        signals: Raw per-signal scores; only signals that fired appear.
        weight: Composed linear-combination score (see module ``COEFF_*``).
    """

    source: str
    target: str
    kind: str
    signals: dict[str, float] = field(default_factory=dict)
    weight: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation of the derived edge.

        Returns:
            Dict with ``source``, ``target``, ``kind``, ``signals``, and
            ``weight`` keys, safe to pass to ``json.dumps``.
        """
        return {
            "source": self.source,
            "target": self.target,
            "kind": self.kind,
            "signals": dict(self.signals),
            "weight": self.weight,
        }


def _real_node_keys(graph: VaultGraph) -> list[str]:
    """Return sorted keys of all non-phantom nodes in *graph*."""
    return sorted(name for name, node in graph.nodes.items() if not node.phantom)


def _non_structural_tags(graph: VaultGraph, name: str) -> frozenset[str]:
    """Return a node's tags excluding directory tags and its feature tag.

    Directory tags (``#adr``, ``#plan``, ``#research`` and the rest) are
    near-universal: almost every document carries exactly one, so sharing one
    would connect essentially everything.  The feature tag is excluded too
    because it is handled by the dedicated ``shared_feature`` signal.

    Args:
        graph: The vault graph holding the node.
        name: Node key to inspect.

    Returns:
        Frozenset of the node's remaining (semantic) tags.
    """
    node = graph.nodes[name]
    feature_tag = f"#{node.feature}" if node.feature else None
    return frozenset(
        tag for tag in node.tags if DocType.from_tag(tag) is None and tag != feature_tag
    )


def _reciprocity_pairs(graph: VaultGraph) -> set[frozenset[str]]:
    """Return undirected pairs that link to each other in both directions.

    Args:
        graph: The vault graph to inspect.

    Returns:
        Set of two-element frozensets ``{a, b}`` where the canonical graph
        holds both ``a -> b`` and ``b -> a`` and neither endpoint is a
        phantom.
    """
    g = graph.digraph
    pairs: set[frozenset[str]] = set()
    for src, tgt in g.edges():
        if (
            g.has_edge(tgt, src)
            and src in graph.nodes
            and tgt in graph.nodes
            and not graph.nodes[src].phantom
            and not graph.nodes[tgt].phantom
        ):
            pairs.add(frozenset((src, tgt)))
    return pairs


def _undirected_projection(graph: VaultGraph) -> nx.Graph:
    """Return an undirected projection over non-phantom nodes only.

    The networkx link-prediction family (Jaccard, Adamic-Adar) operates on an
    undirected graph.  Phantom nodes are dropped so relatedness is computed
    purely over real documents.

    Args:
        graph: The vault graph to project.

    Returns:
        An undirected ``nx.Graph`` whose nodes are the real document keys and
        whose edges mirror the canonical directed edges between real nodes.
    """
    reals = {name for name, node in graph.nodes.items() if not node.phantom}
    sub = graph.digraph.subgraph(reals)
    return sub.to_undirected()


def _co_citation_counts(graph: VaultGraph) -> dict[frozenset[str], int]:
    """Return co-citation counts: shared predecessors per undirected pair.

    Two documents are co-cited when a third document references both of them.
    The count is the number of distinct documents that link to both endpoints
    (the size of their common-predecessor set in the directed graph).

    Args:
        graph: The vault graph to inspect.

    Returns:
        Mapping from an undirected ``{a, b}`` pair to the number of shared
        predecessors; only pairs with at least one shared predecessor appear.
    """
    g = graph.digraph
    counts: dict[frozenset[str], int] = {}
    for citing in g.nodes():
        if citing in graph.nodes and graph.nodes[citing].phantom:
            continue
        cited = sorted(
            tgt
            for tgt in g.successors(citing)
            if tgt in graph.nodes and not graph.nodes[tgt].phantom
        )
        for a, b in itertools.combinations(cited, 2):
            key = frozenset((a, b))
            counts[key] = counts.get(key, 0) + 1
    return counts


def _compose_weight(signals: dict[str, float]) -> float:
    """Return the linear-combination weight for a signal map.

    Args:
        signals: Raw per-signal scores (absent signals count as 0.0).

    Returns:
        The composed weight using the version-pinned ``COEFF_*`` constants.
    """
    return (
        COEFF_RECIPROCITY * signals.get("reciprocity", 0.0)
        + COEFF_SHARED_FEATURE * signals.get("shared_feature", 0.0)
        + COEFF_SHARED_TAG * signals.get("shared_tag", 0.0)
        + COEFF_JACCARD * signals.get("jaccard", 0.0)
        + COEFF_ADAMIC_ADAR * signals.get("adamic_adar", 0.0)
        + COEFF_CO_CITATION * signals.get("co_citation", 0.0)
    )


def _dominant_kind(signals: dict[str, float]) -> str:
    """Return the provenance label of the highest-coefficient-weighted signal.

    The dominant signal is the one contributing the most to the composed
    weight (raw score times its coefficient).  Ties break by a fixed signal
    priority order so the result is deterministic.

    Args:
        signals: Raw per-signal scores.

    Returns:
        The name of the dominant contributing signal.
    """
    contributions = {
        "reciprocity": COEFF_RECIPROCITY * signals.get("reciprocity", 0.0),
        "shared_feature": COEFF_SHARED_FEATURE * signals.get("shared_feature", 0.0),
        "shared_tag": COEFF_SHARED_TAG * signals.get("shared_tag", 0.0),
        "jaccard": COEFF_JACCARD * signals.get("jaccard", 0.0),
        "adamic_adar": COEFF_ADAMIC_ADAR * signals.get("adamic_adar", 0.0),
        "co_citation": COEFF_CO_CITATION * signals.get("co_citation", 0.0),
    }
    priority = (
        "reciprocity",
        "shared_feature",
        "jaccard",
        "co_citation",
        "shared_tag",
        "adamic_adar",
    )
    present = {name: contributions[name] for name in signals}
    if not present:
        return "none"
    best = max(present.values())
    for name in priority:
        if name in present and present[name] == best:
            return name
    # Fallback: deterministic by sorted signal name.
    return sorted(present)[0]


def compute_derived_edges(graph: VaultGraph) -> list[DerivedEdge]:
    """Compute the full derived relatedness edge set for *graph*.

    Builds one :class:`DerivedEdge` per undirected real-document pair that
    fires at least one relatedness signal.  Signals computed:

    - ``reciprocity``: ``1.0`` when both directed edges exist between the pair.
    - ``shared_feature``: ``1.0`` when both documents share a feature tag.
    - ``shared_tag``: count of shared semantic (non-directory, non-feature)
      tags, as a float.
    - ``jaccard``: ``nx.jaccard_coefficient`` on the undirected projection.
    - ``adamic_adar``: ``nx.adamic_adar_index`` on the undirected projection.
    - ``co_citation``: number of documents referencing both endpoints.

    The canonical DiGraph is never mutated.  The returned list is sorted by
    descending composed weight then by endpoints, so the ordering is
    deterministic.

    Args:
        graph: The :class:`~vaultspec_core.graph.api.VaultGraph` to analyse.

    Returns:
        Deterministically ordered list of :class:`DerivedEdge` instances; one
        per pair with at least one non-zero signal.
    """
    reals = _real_node_keys(graph)
    undirected = _undirected_projection(graph)

    reciprocity = _reciprocity_pairs(graph)
    co_citation = _co_citation_counts(graph)

    # networkx link-prediction over every non-adjacent and adjacent real pair.
    # jaccard_coefficient / adamic_adar_index accept an explicit ebunch so we
    # evaluate exactly the candidate pairs (all unordered real pairs).
    candidate_pairs = list(itertools.combinations(reals, 2))
    jaccard = {
        frozenset((u, v)): score
        for u, v, score in nx.jaccard_coefficient(undirected, candidate_pairs)
    }
    adamic = {
        frozenset((u, v)): score
        for u, v, score in nx.adamic_adar_index(undirected, candidate_pairs)
    }

    edges: list[DerivedEdge] = []
    for a, b in candidate_pairs:
        key = frozenset((a, b))
        signals: dict[str, float] = {}

        if key in reciprocity:
            signals["reciprocity"] = 1.0

        node_a = graph.nodes[a]
        node_b = graph.nodes[b]
        if node_a.feature and node_a.feature == node_b.feature:
            signals["shared_feature"] = 1.0

        shared = _non_structural_tags(graph, a) & _non_structural_tags(graph, b)
        if shared:
            signals["shared_tag"] = float(len(shared))

        j = jaccard.get(key, 0.0)
        if j:
            signals["jaccard"] = j

        aa = adamic.get(key, 0.0)
        if aa:
            signals["adamic_adar"] = aa

        cc = co_citation.get(key, 0)
        if cc:
            signals["co_citation"] = float(cc)

        if not signals:
            continue

        src, tgt = sorted((a, b))
        edges.append(
            DerivedEdge(
                source=src,
                target=tgt,
                kind=_dominant_kind(signals),
                signals=signals,
                weight=_compose_weight(signals),
            )
        )

    edges.sort(key=lambda e: (-e.weight, e.source, e.target))
    return edges
