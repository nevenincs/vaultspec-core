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
