"""Exact-value tests for the derived relatedness edge set.

Every signal (reciprocity, shared-feature, shared-tag, jaccard, adamic-adar,
co-citation) and the composed weight are asserted against hand-derivable real
values built from small on-disk vaults.  No mocks: every graph is a real
:class:`~vaultspec_core.graph.api.VaultGraph` over real markdown files, and the
networkx link-prediction scores are deterministic for the fixed structures.
"""

import math
from pathlib import Path

import pytest

from ...graph import VaultGraph
from ...graph.derived import (
    COEFF_ADAMIC_ADAR,
    COEFF_CO_CITATION,
    COEFF_JACCARD,
    COEFF_RECIPROCITY,
    COEFF_SHARED_FEATURE,
    COEFF_SHARED_TAG,
    DerivedEdge,
    compute_derived_edges,
)

pytestmark = [pytest.mark.unit]


def _write(path: Path, tags: list[str], related: str = "") -> None:
    """Write a minimal vault document with *tags* and optional *related*."""
    fm = "---\ntags:\n" + "".join(f'  - "{t}"\n' for t in tags) + "date: 2026-01-01\n"
    fm += f"related:\n{related}\n" if related else "related: []\n"
    fm += "---\n\n# " + path.stem + "\n"
    path.write_text(fm, encoding="utf-8")


def _edge_map(graph: VaultGraph) -> dict[tuple[str, str], DerivedEdge]:
    """Index derived edges by their ``(source, target)`` endpoints."""
    return {(e.source, e.target): e for e in compute_derived_edges(graph)}


class TestReciprocitySignal:
    """Mutual references fire reciprocity in isolation."""

    def _graph(self, tmp_path: Path) -> VaultGraph:
        vault = tmp_path / ".vault"
        (vault / "adr").mkdir(parents=True)
        (vault / "plan").mkdir()
        # Distinct features so only reciprocity fires.
        _write(vault / "adr" / "recip-x.md", ["#adr", "#feat-x"], '  - "[[recip-y]]"')
        _write(vault / "plan" / "recip-y.md", ["#plan", "#feat-y"], '  - "[[recip-x]]"')
        return VaultGraph(tmp_path)

    def test_reciprocity_score_is_one(self, tmp_path):
        edge = _edge_map(self._graph(tmp_path))[("recip-x", "recip-y")]
        assert edge.signals["reciprocity"] == 1.0

    def test_reciprocity_is_the_only_signal(self, tmp_path):
        edge = _edge_map(self._graph(tmp_path))[("recip-x", "recip-y")]
        # Two mutually-linked nodes are each other's only neighbour, so they
        # have no common neighbour: the undirected Jaccard is 0 and no
        # link-prediction signal fires.  Distinct features and tags mean
        # reciprocity is the sole relatedness signal.
        assert set(edge.signals) == {"reciprocity"}

    def test_reciprocity_weight_is_exact(self, tmp_path):
        edge = _edge_map(self._graph(tmp_path))[("recip-x", "recip-y")]
        assert edge.weight == COEFF_RECIPROCITY * 1.0
        assert edge.kind == "reciprocity"


class TestSharedFeatureSignal:
    """Two documents in the same feature fire shared-feature."""

    def test_shared_feature_score_is_one(self, tmp_path):
        vault = tmp_path / ".vault"
        (vault / "adr").mkdir(parents=True)
        (vault / "plan").mkdir()
        _write(vault / "adr" / "sf-a.md", ["#adr", "#feat-same"])
        _write(vault / "plan" / "sf-b.md", ["#plan", "#feat-same"])
        edge = _edge_map(VaultGraph(tmp_path))[("sf-a", "sf-b")]
        assert edge.signals["shared_feature"] == 1.0
        assert edge.weight == COEFF_SHARED_FEATURE * 1.0


class TestSharedTagSignal:
    """A shared non-feature, non-directory tag fires shared-tag.

    Both documents carry identical non-directory tag sets so the feature tag
    is assigned identically and the remaining semantic tag is shared.
    """

    def _graph(self, tmp_path: Path) -> VaultGraph:
        vault = tmp_path / ".vault"
        (vault / "adr").mkdir(parents=True)
        (vault / "plan").mkdir()
        _write(vault / "adr" / "st-a.md", ["#adr", "#feat-shared", "#topic-x"])
        _write(vault / "plan" / "st-b.md", ["#plan", "#feat-shared", "#topic-x"])
        return VaultGraph(tmp_path)

    def test_shared_tag_counts_the_shared_semantic_tag(self, tmp_path):
        edge = _edge_map(self._graph(tmp_path))[("st-a", "st-b")]
        assert edge.signals["shared_tag"] == 1.0

    def test_shared_feature_and_tag_compose_exactly(self, tmp_path):
        edge = _edge_map(self._graph(tmp_path))[("st-a", "st-b")]
        # The pair shares the feature and one extra semantic tag.
        assert edge.signals["shared_feature"] == 1.0
        assert edge.signals["shared_tag"] == 1.0
        expected = COEFF_SHARED_FEATURE * 1.0 + COEFF_SHARED_TAG * 1.0
        assert edge.weight == expected


class TestLinkPredictionAndCoCitation:
    """A co-citing hub fires jaccard, adamic-adar, and co-citation.

    ``hub`` references both ``doc-a`` and ``doc-b``; the two cited documents
    share exactly one common neighbour (the hub) in the undirected projection
    and one common predecessor (the hub) in the directed graph.  All three
    share the same feature too.
    """

    def _graph(self, tmp_path: Path) -> VaultGraph:
        vault = tmp_path / ".vault"
        (vault / "research").mkdir(parents=True)
        (vault / "adr").mkdir()
        (vault / "plan").mkdir()
        _write(
            vault / "research" / "hub.md",
            ["#research", "#feat-h"],
            '  - "[[doc-a]]"\n  - "[[doc-b]]"',
        )
        _write(vault / "adr" / "doc-a.md", ["#adr", "#feat-h"])
        _write(vault / "plan" / "doc-b.md", ["#plan", "#feat-h"])
        return VaultGraph(tmp_path)

    def test_jaccard_is_one_for_single_shared_neighbour(self, tmp_path):
        edge = _edge_map(self._graph(tmp_path))[("doc-a", "doc-b")]
        # Each cited doc has exactly the hub as its sole neighbour, so the
        # Jaccard coefficient is |{hub}| / |{hub}| = 1.0.
        assert edge.signals["jaccard"] == 1.0

    def test_adamic_adar_is_inverse_log_of_hub_degree(self, tmp_path):
        edge = _edge_map(self._graph(tmp_path))[("doc-a", "doc-b")]
        # The single common neighbour (hub) has undirected degree 2, so
        # Adamic-Adar = 1 / ln(2).
        assert edge.signals["adamic_adar"] == 1.0 / math.log(2)

    def test_co_citation_counts_the_single_shared_predecessor(self, tmp_path):
        edge = _edge_map(self._graph(tmp_path))[("doc-a", "doc-b")]
        assert edge.signals["co_citation"] == 1.0

    def test_composed_weight_is_exact_linear_combination(self, tmp_path):
        edge = _edge_map(self._graph(tmp_path))[("doc-a", "doc-b")]
        expected = (
            COEFF_SHARED_FEATURE * 1.0
            + COEFF_JACCARD * 1.0
            + COEFF_ADAMIC_ADAR * (1.0 / math.log(2))
            + COEFF_CO_CITATION * 1.0
        )
        assert edge.weight == expected

    def test_no_self_or_hub_pair_signals_inflate(self, tmp_path):
        edge = _edge_map(self._graph(tmp_path))[("doc-a", "doc-b")]
        # Exactly the four expected signals fire; reciprocity and shared_tag
        # do not (no mutual edge, no extra shared tag).
        assert set(edge.signals) == {
            "shared_feature",
            "jaccard",
            "adamic_adar",
            "co_citation",
        }


class TestDerivedEdgeDeterminismAndOrdering:
    """The derived edge set is deterministic and weight-ordered."""

    def _graph(self, tmp_path: Path) -> VaultGraph:
        vault = tmp_path / ".vault"
        (vault / "research").mkdir(parents=True)
        (vault / "adr").mkdir()
        (vault / "plan").mkdir()
        _write(
            vault / "research" / "hub.md",
            ["#research", "#feat-h"],
            '  - "[[doc-a]]"\n  - "[[doc-b]]"',
        )
        _write(vault / "adr" / "doc-a.md", ["#adr", "#feat-h"])
        _write(vault / "plan" / "doc-b.md", ["#plan", "#feat-h"])
        return VaultGraph(tmp_path)

    def test_repeated_computation_is_identical(self, tmp_path):
        graph = self._graph(tmp_path)
        first = [(e.source, e.target, e.weight) for e in compute_derived_edges(graph)]
        second = [(e.source, e.target, e.weight) for e in compute_derived_edges(graph)]
        assert first == second

    def test_edges_sorted_by_descending_weight(self, tmp_path):
        edges = compute_derived_edges(self._graph(tmp_path))
        weights = [e.weight for e in edges]
        assert weights == sorted(weights, reverse=True)

    def test_endpoints_are_sorted_within_each_edge(self, tmp_path):
        edges = compute_derived_edges(self._graph(tmp_path))
        for edge in edges:
            assert edge.source < edge.target

    def test_to_dict_round_trips_fields(self, tmp_path):
        edge = _edge_map(self._graph(tmp_path))[("doc-a", "doc-b")]
        d = edge.to_dict()
        assert d["source"] == "doc-a"
        assert d["target"] == "doc-b"
        assert d["kind"] == edge.kind
        assert d["weight"] == edge.weight
        assert d["signals"] == edge.signals


class TestScopedComputation:
    """A scoped derived computation runs over the scoped node set alone.

    The crafted vault has a hub citing four documents (``doc-a``..``doc-d``);
    all five share a feature.  Scoping the computation to ``{doc-a, doc-b}``
    must (a) emit only the single ``doc-a``/``doc-b`` edge - never any edge
    touching ``doc-c`` or ``doc-d`` or the hub - and (b) preserve the
    scope-invariant signals (shared-feature, co-citation) at exactly the values
    the whole-graph computation produces for that pair.
    """

    def _graph(self, tmp_path: Path) -> VaultGraph:
        vault = tmp_path / ".vault"
        (vault / "research").mkdir(parents=True)
        (vault / "adr").mkdir()
        (vault / "plan").mkdir()
        _write(
            vault / "research" / "hub.md",
            ["#research", "#feat-h"],
            '  - "[[doc-a]]"\n  - "[[doc-b]]"\n  - "[[doc-c]]"\n  - "[[doc-d]]"',
        )
        _write(vault / "adr" / "doc-a.md", ["#adr", "#feat-h"])
        _write(vault / "plan" / "doc-b.md", ["#plan", "#feat-h"])
        _write(vault / "adr" / "doc-c.md", ["#adr", "#feat-h"])
        _write(vault / "plan" / "doc-d.md", ["#plan", "#feat-h"])
        return VaultGraph(tmp_path)

    def test_scope_emits_only_in_scope_pairs(self, tmp_path):
        graph = self._graph(tmp_path)
        scope = {"doc-a", "doc-b"}
        scoped = compute_derived_edges(graph, scope)
        # Exactly one pair is in scope: (doc-a, doc-b).  No edge may touch any
        # out-of-scope node (doc-c, doc-d, hub).
        assert [(e.source, e.target) for e in scoped] == [("doc-a", "doc-b")]
        for edge in scoped:
            assert edge.source in scope
            assert edge.target in scope

    def test_scope_does_not_enumerate_full_pair_set(self, tmp_path):
        graph = self._graph(tmp_path)
        # The full computation enumerates every real pair: C(5, 2) = 10 pairs
        # over {hub, doc-a, doc-b, doc-c, doc-d}, all sharing the feature, so
        # all 10 fire and 10 edges are emitted.  The N=2 scope emits exactly 1.
        full = compute_derived_edges(graph)
        assert len(full) == 10
        scoped = compute_derived_edges(graph, {"doc-a", "doc-b"})
        assert len(scoped) == 1

    def test_scope_invariant_signals_match_full_for_the_pair(self, tmp_path):
        graph = self._graph(tmp_path)
        full = _edge_map(graph)[("doc-a", "doc-b")]
        scoped = {
            (e.source, e.target): e
            for e in compute_derived_edges(graph, {"doc-a", "doc-b"})
        }[("doc-a", "doc-b")]
        # shared_feature and co_citation depend only on the endpoints (and any
        # citing document anywhere), so they are scope-invariant: the hub still
        # co-cites doc-a and doc-b even though the hub is out of scope.
        assert scoped.signals["shared_feature"] == full.signals["shared_feature"]
        assert scoped.signals["co_citation"] == full.signals["co_citation"]
        assert scoped.signals["co_citation"] == 1.0

    def test_projection_relative_signals_differ_under_scope(self, tmp_path):
        graph = self._graph(tmp_path)
        full = _edge_map(graph)[("doc-a", "doc-b")]
        scoped = {
            (e.source, e.target): e
            for e in compute_derived_edges(graph, {"doc-a", "doc-b"})
        }[("doc-a", "doc-b")]
        # In the whole-graph projection doc-a and doc-b share the hub as a
        # common neighbour, so jaccard and adamic-adar fire.  Restricting the
        # projection to {doc-a, doc-b} drops the hub from the projection, so
        # the two nodes have no edge and no common neighbour: both
        # projection-relative signals vanish.  This is the documented
        # local-neighbourhood semantics, not a bug.
        assert "jaccard" in full.signals
        assert "adamic_adar" in full.signals
        assert "jaccard" not in scoped.signals
        assert "adamic_adar" not in scoped.signals

    def test_none_scope_is_whole_graph(self, tmp_path):
        graph = self._graph(tmp_path)
        explicit = [
            (e.source, e.target, e.weight) for e in compute_derived_edges(graph, None)
        ]
        implicit = [
            (e.source, e.target, e.weight) for e in compute_derived_edges(graph)
        ]
        assert explicit == implicit


class TestScopedToDictExport:
    """``to_dict`` scoping flows the exported node set into the derived pass."""

    def _graph(self, tmp_path: Path) -> VaultGraph:
        vault = tmp_path / ".vault"
        (vault / "research").mkdir(parents=True)
        (vault / "adr").mkdir()
        (vault / "plan").mkdir()
        _write(
            vault / "research" / "hub.md",
            ["#research", "#feat-h"],
            '  - "[[doc-a]]"\n  - "[[doc-b]]"\n  - "[[doc-c]]"',
        )
        _write(vault / "adr" / "doc-a.md", ["#adr", "#feat-h"])
        _write(vault / "plan" / "doc-b.md", ["#plan", "#feat-h"])
        _write(vault / "adr" / "doc-c.md", ["#adr", "#feat-other"])
        return VaultGraph(tmp_path)

    def test_ego_export_only_carries_in_neighbourhood_derived_edges(self, tmp_path):
        graph = self._graph(tmp_path)
        # Ego around doc-a at depth 1 reaches the hub and, through it, doc-b and
        # doc-c.  Every derived edge in the payload must have both endpoints in
        # the exported node set.
        data = graph.to_dict(node="doc-a", depth=1)
        exported = {n["id"] for n in data["nodes"]}
        for edge in data["derived_edges"]:
            assert edge["source"] in exported
            assert edge["target"] in exported

    def test_full_export_derived_count_matches_unscoped_compute(self, tmp_path):
        graph = self._graph(tmp_path)
        data = graph.to_dict()
        assert len(data["derived_edges"]) == len(compute_derived_edges(graph))


class TestDerivedEdgesNeverEnterCanonicalGraph:
    """The canonical DiGraph holds no synthetic relatedness edges."""

    def test_canonical_graph_has_no_derived_edge(self, tmp_path):
        vault = tmp_path / ".vault"
        (vault / "research").mkdir(parents=True)
        (vault / "adr").mkdir()
        (vault / "plan").mkdir()
        _write(
            vault / "research" / "hub.md",
            ["#research", "#feat-h"],
            '  - "[[doc-a]]"\n  - "[[doc-b]]"',
        )
        _write(vault / "adr" / "doc-a.md", ["#adr", "#feat-h"])
        _write(vault / "plan" / "doc-b.md", ["#plan", "#feat-h"])
        graph = VaultGraph(tmp_path)
        derived = compute_derived_edges(graph)
        assert any(e.source == "doc-a" and e.target == "doc-b" for e in derived)
        # The relatedness edge exists in the derived set but never in the
        # canonical directed graph (no real reference connects doc-a/doc-b).
        assert not graph.digraph.has_edge("doc-a", "doc-b")
        assert not graph.digraph.has_edge("doc-b", "doc-a")
