"""Tests for the descriptive-counts surface and its render-path contract.

Two invariants from the counts-vs-analysis split:

1. :meth:`~vaultspec_core.graph.api.VaultGraph.counts` reports exactly the
   ``total_nodes``, ``total_edges``, and ``total_features`` values
   :meth:`~vaultspec_core.graph.api.VaultGraph.metrics` reports, scoped and
   unscoped, so the tree title is byte-identical to what the conflated path
   produced.
2. The render path never invokes graph-theoretic analysis.  This is
   asserted by counting real calls with ``sys.setprofile`` - observation of
   the genuine execution, not a stub - while ``render_tree`` runs.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest

from ...config import reset_config
from ...testing.synthetic import build_synthetic_vault
from ..api import VaultGraph

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]


@pytest.fixture
def vault_root(tmp_path: Path) -> Path:
    reset_config()
    build_synthetic_vault(
        tmp_path,
        n_docs=40,
        seed=13,
        pathologies=["cycle", "stem_collision", "phantom_only_links"],
    )
    return tmp_path


class TestCountsMatchMetrics:
    def test_unscoped_counts_equal_metrics(self, vault_root: Path) -> None:
        graph = VaultGraph(vault_root, use_cache=False)
        c = graph.counts()
        m = graph.metrics()
        assert c.docs == m.total_nodes
        assert c.links == m.total_edges
        assert c.features == m.total_features
        assert c.docs > 0
        assert c.features > 0

    def test_feature_scoped_counts_equal_metrics(self, vault_root: Path) -> None:
        graph = VaultGraph(vault_root, use_cache=False)
        for feature in graph.get_features():
            c = graph.counts(feature=feature)
            m = graph.metrics(feature=feature)
            assert c.docs == m.total_nodes, feature
            assert c.links == m.total_edges, feature


class TestRenderPathBuysNoAnalysis:
    def test_render_tree_never_calls_centrality(
        self, vault_root: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        graph = VaultGraph(vault_root, use_cache=False)
        analysis_calls: list[str] = []

        def profiler(frame, event: str, arg: object) -> None:
            if event == "call" and frame.f_code.co_name in (
                "betweenness_centrality",
                "in_degree_centrality",
                "metrics",
            ):
                analysis_calls.append(frame.f_code.co_name)

        sys.setprofile(profiler)
        try:
            graph.render_tree()
            graph.render_tree(feature=graph.get_features()[0])
        finally:
            sys.setprofile(None)

        assert analysis_calls == []
        out = capsys.readouterr().out
        assert " docs, " in out and " links" in out
