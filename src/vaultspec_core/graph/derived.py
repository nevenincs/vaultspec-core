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
from typing import TYPE_CHECKING, Any, cast

import networkx as nx

from ..vaultcore import DocType

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from .api import VaultGraph
    from .networkx_runtime import NetworkXGraph

# networkx's bundled type stubs leave the link-prediction dispatchables
# (`jaccard_coefficient`, `adamic_adar_index`) untyped - each is a runtime
# backend-dispatch descriptor whose declared return type is `Unknown`, not a
# gap this module can close by annotating call sites. A dict lookup retrieves
# the same callable without tripping that stub-only "partially unknown"
# report, and the `Callable` annotation below is the real, hand-verified
# signature: both functions accept the graph and an explicit `ebunch` and
# yield `(node, node, score)` triples.
_jaccard_coefficient: Callable[
    [NetworkXGraph, list[tuple[str, str]]], Iterable[tuple[str, str, float]]
] = nx.__dict__["jaccard_coefficient"]
_adamic_adar_index: Callable[
    [NetworkXGraph, list[tuple[str, str]]], Iterable[tuple[str, str, float]]
] = nx.__dict__["adamic_adar_index"]

__all__ = [
    "COEFFICIENTS_VERSION",
    "COEFF_ADAMIC_ADAR",
    "COEFF_CO_CITATION",
    "COEFF_JACCARD",
    "COEFF_RECIPROCITY",
    "COEFF_SHARED_FEATURE",
    "COEFF_SHARED_TAG",
    "DEFAULT_TOP_K",
    "DerivedEdge",
    "compute_derived_edges",
    "trim_to_top_k",
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


def _real_node_keys(
    graph: VaultGraph,
    scope: set[str] | None = None,
) -> list[str]:
    """Return sorted keys of non-phantom nodes, optionally scoped.

    Args:
        graph: The vault graph to inspect.
        scope: When set, restrict the result to keys present in *scope*; when
            ``None`` (the default) every non-phantom node is returned.

    Returns:
        Sorted list of non-phantom node keys, intersected with *scope* when one
        is given.
    """
    return sorted(
        name
        for name, node in graph.nodes.items()
        if not node.phantom and (scope is None or name in scope)
    )


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


def _reciprocity_pairs(
    graph: VaultGraph,
    scope: set[str] | None = None,
) -> set[frozenset[str]]:
    """Return undirected pairs that link to each other in both directions.

    Args:
        graph: The vault graph to inspect.
        scope: When set, only pairs whose endpoints both lie in *scope* are
            returned; when ``None`` every reciprocal real pair is returned.

    Returns:
        Set of two-element frozensets ``{a, b}`` where the canonical graph
        holds both ``a -> b`` and ``b -> a`` and neither endpoint is a
        phantom.
    """
    g = graph.digraph
    pairs: set[frozenset[str]] = set()
    for src, tgt in g.edges():
        if scope is not None and (src not in scope or tgt not in scope):
            continue
        if (
            g.has_edge(tgt, src)
            and src in graph.nodes
            and tgt in graph.nodes
            and not graph.nodes[src].phantom
            and not graph.nodes[tgt].phantom
        ):
            pairs.add(frozenset((src, tgt)))
    return pairs


def _undirected_projection(
    graph: VaultGraph,
    scope: set[str] | None = None,
) -> NetworkXGraph:
    """Return an undirected projection over non-phantom nodes only.

    The networkx link-prediction family (Jaccard, Adamic-Adar) operates on an
    undirected graph.  Phantom nodes are dropped so relatedness is computed
    purely over real documents.

    When *scope* is supplied the projection is restricted to those nodes, so
    the shared-neighbour structure that Jaccard and Adamic-Adar consume is the
    local-neighbourhood structure rather than the whole-graph structure.  That
    is a deliberate semantic choice for a scoped (ego or feature) view: these
    two signals are projection-relative and therefore differ from their
    whole-graph values once the projection is restricted.

    Args:
        graph: The vault graph to project.
        scope: When set, restrict the projected node set to *scope*; when
            ``None`` every real node is projected.

    Returns:
        An undirected ``nx.Graph`` whose nodes are the in-scope real document
        keys and whose edges mirror the canonical directed edges between them.
    """
    reals = {
        name
        for name, node in graph.nodes.items()
        if not node.phantom and (scope is None or name in scope)
    }
    sub = graph.digraph.subgraph(reals)
    return sub.to_undirected()


def _co_citation_counts(
    graph: VaultGraph,
    scope: set[str] | None = None,
) -> dict[frozenset[str], int]:
    """Return co-citation counts: shared predecessors per undirected pair.

    Two documents are co-cited when a third document references both of them.
    The count is the number of distinct documents that link to both endpoints
    (the size of their common-predecessor set in the directed graph).

    The citing (hub) document is never restricted to *scope*: a document
    outside the scoped view that references two in-scope documents still
    co-cites them.  Only the counted *endpoint* pair is restricted to *scope*,
    so the scoped result equals the whole-graph result filtered to the scoped
    pairs - co-citation is scope-invariant.

    Args:
        graph: The vault graph to inspect.
        scope: When set, only count pairs whose endpoints both lie in *scope*;
            when ``None`` every real pair is counted.

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
            if tgt in graph.nodes
            and not graph.nodes[tgt].phantom
            and (scope is None or tgt in scope)
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


def _candidate_pairs(
    graph: VaultGraph,
    reals: list[str],
    undirected: NetworkXGraph,
    reciprocity: set[frozenset[str]],
    co_citation: dict[frozenset[str], int],
) -> list[tuple[str, str]]:
    """Return every pair that can carry a signal, and no others.

    The generator used to enumerate ``itertools.combinations(reals, 2)`` - every
    unordered pair in the vault - score them all, and discard the ones with no
    signal. At 1,243 nodes that materialised 772,003 pairs to emit 23,499; at
    10,476 nodes it is 54.9 million pairs and the command did not return inside
    twenty minutes.

    Every signal is sparse, so the pairs that can score are enumerable directly:

    * ``reciprocity`` and ``co_citation`` arrive as pair-keyed maps already.
    * ``jaccard`` and ``adamic_adar`` are zero unless two nodes share a
      neighbour, so the candidates are the pairs drawn from each node's
      neighbourhood - ``sum(deg^2)`` rather than ``n^2``.
    * ``shared_feature`` and ``shared_tag`` are pairs within a feature or a tag,
      enumerable per group.

    The union is exactly the set the old code kept, so the emitted edges are
    unchanged; only the pairs that were always going to be discarded are never
    built.

    Args:
        graph: The graph being analysed.
        reals: Non-phantom node keys in scope.
        undirected: The undirected projection used for link prediction.
        reciprocity: Pairs linking each other in both directions.
        co_citation: Pair-keyed co-citation counts.

    Returns:
        Deterministically ordered candidate pairs.
    """
    in_scope = set(reals)
    pairs: set[frozenset[str]] = set()

    pairs.update(pair for pair in reciprocity if len(pair) == 2)
    pairs.update(pair for pair in co_citation if len(pair) == 2)

    # Shared-neighbour pairs: the only ones where jaccard or adamic-adar can be
    # non-zero. A node of degree d contributes C(d, 2) pairs, so this is bounded
    # by the graph's actual connectivity rather than by its size.
    for hub in cast("list[str]", list(undirected.nodes)):
        neighbours: list[str] = sorted(
            n
            for n in cast("list[str]", list(undirected.neighbors(hub)))
            if n in in_scope
        )
        for i, u in enumerate(neighbours):
            for v in neighbours[i + 1 :]:
                pairs.add(frozenset((u, v)))

    # Same-feature and same-tag pairs, grouped rather than filtered.
    by_feature: dict[str, list[str]] = {}
    by_tag: dict[str, list[str]] = {}
    for name in reals:
        node = graph.nodes[name]
        if node.feature:
            by_feature.setdefault(node.feature, []).append(name)
        for tag in _non_structural_tags(graph, name):
            by_tag.setdefault(tag, []).append(name)

    for group in (*by_feature.values(), *by_tag.values()):
        for u, v in itertools.combinations(sorted(group), 2):
            pairs.add(frozenset((u, v)))

    ordered: list[tuple[str, str]] = []
    for pair in pairs:
        if len(pair) != 2 or not pair <= in_scope:
            continue
        u, v = sorted(pair)
        ordered.append((u, v))
    return sorted(ordered)


#: Derived edges kept per node when a fan-out cap is applied.
#:
#: Derived edges are a *ranking*, not vault state: they are a similarity
#: product recomputed from the graph on demand. An exhaustive ranking is not
#: more useful than a good one, and it is unbounded - at 10,476 documents the
#: full set is 1,011,120 edges and 261 MB of payload, 94% of the export. Eight
#: neighbours is enough to answer "what else is like this" for any one node.
DEFAULT_TOP_K = 8


def trim_to_top_k(
    edges: list[DerivedEdge], top_k: int = DEFAULT_TOP_K
) -> list[DerivedEdge]:
    """Keep only each node's strongest *top_k* derived edges.

    An edge survives while **either** endpoint still has room. The consequence
    worth stating: a node's only edge is never dropped, because the node has
    not yet spent its own quota - so this caps fan-out between well-connected
    nodes and leaves the periphery intact. Requiring *both* endpoints to have
    room would cap harder but strand weakly-connected documents, which is where
    a relatedness ranking earns its keep.

    It is therefore a fan-out cap, not a hard edge budget: the retained count
    is bounded by roughly ``nodes x top_k`` rather than by ``top_k``. Measured
    on a 10,476-document vault it retained 68,878 of 1,011,120 edges.

    Args:
        edges: Derived edges, already sorted strongest first.
        top_k: Edges to keep per node. Non-positive disables the cap.

    Returns:
        The retained edges, in the input's order.
    """
    if top_k <= 0:
        return edges
    seen: dict[str, int] = {}
    kept: list[DerivedEdge] = []
    for edge in edges:
        a = seen.get(edge.source, 0)
        b = seen.get(edge.target, 0)
        if a < top_k or b < top_k:
            kept.append(edge)
            seen[edge.source] = a + 1
            seen[edge.target] = b + 1
    return kept


def compute_derived_edges(
    graph: VaultGraph,
    scope: set[str] | None = None,
) -> list[DerivedEdge]:
    """Compute the derived relatedness edge set for *graph*.

    Builds one :class:`DerivedEdge` per undirected real-document pair that
    fires at least one relatedness signal.  Signals computed:

    - ``reciprocity``: ``1.0`` when both directed edges exist between the pair.
    - ``shared_feature``: ``1.0`` when both documents share a feature tag.
    - ``shared_tag``: count of shared semantic (non-directory, non-feature)
      tags, as a float.
    - ``jaccard``: ``nx.jaccard_coefficient`` on the undirected projection.
    - ``adamic_adar``: ``nx.adamic_adar_index`` on the undirected projection.
    - ``co_citation``: number of documents referencing both endpoints.

    Scoping semantics.  When *scope* is ``None`` the computation runs over the
    whole graph (the historical behaviour).  When *scope* is a set of node
    keys - the node set of a feature- or ego-scoped export - the candidate pair
    set, the reciprocity scan, the co-citation scan, and the undirected
    projection are all built from the scoped node set alone.  The enclosing
    export never pays the whole-graph ``O(n^2)`` pair cost just to throw most
    of the result away.

    Two relatedness families behave differently under scoping, and the
    difference is deliberate:

    - **Scope-invariant signals** - ``reciprocity``, ``shared_feature``,
      ``shared_tag``, and ``co_citation`` - depend only on the two endpoints
      (and, for co-citation, on any citing document anywhere in the graph).
      Their scoped values equal the whole-graph values filtered to the scoped
      pairs.

    - **Projection-relative signals** - ``jaccard`` and ``adamic_adar`` - are
      neighbourhood statistics over the undirected projection.  Restricting the
      projection to the scoped node set restricts the shared-neighbour
      structure they read, so their scoped values are computed within the local
      neighbourhood and legitimately differ from their whole-graph values.  For
      a local graph view this is the intended semantics: relatedness is the
      relatedness *within the neighbourhood being viewed*.

    The canonical DiGraph is never mutated.  The returned list is sorted by
    descending composed weight then by endpoints, so the ordering is
    deterministic.

    Args:
        graph: The :class:`~vaultspec_core.graph.api.VaultGraph` to analyse.
        scope: When set, restrict the computation to this node set (see the
            scoping semantics above); when ``None``, run over the whole graph.

    Returns:
        Deterministically ordered list of :class:`DerivedEdge` instances; one
        per pair with at least one non-zero signal.
    """
    reals = _real_node_keys(graph, scope)
    undirected = _undirected_projection(graph, scope)

    reciprocity = _reciprocity_pairs(graph, scope)
    co_citation = _co_citation_counts(graph, scope)

    # networkx link-prediction over every non-adjacent and adjacent real pair.
    # jaccard_coefficient / adamic_adar_index accept an explicit ebunch so we
    # evaluate exactly the candidate pairs (all unordered real pairs).
    candidate_pairs = _candidate_pairs(
        graph, reals, undirected, reciprocity, co_citation
    )
    jaccard = {
        frozenset((u, v)): score
        for u, v, score in _jaccard_coefficient(undirected, candidate_pairs)
    }
    adamic = {
        frozenset((u, v)): score
        for u, v, score in _adamic_adar_index(undirected, candidate_pairs)
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
