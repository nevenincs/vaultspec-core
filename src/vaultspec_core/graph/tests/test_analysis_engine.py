"""Engine parity for the opt-in betweenness analysis surface.

The analysis seam routes betweenness centrality through the C-backed
rustworkx engine with pure networkx as the fallback. Both engines
implement Brandes with the same directed normalisation, so their scores
must agree to float tolerance on a real corpus - this test runs BOTH real
engines on the same built graph and compares, mock-free. A divergence
means the seam changed semantics, not just speed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import networkx as nx
import pytest

from ...config import reset_config
from ...testing.synthetic import build_synthetic_vault
from ..api import VaultGraph, _betweenness_centrality

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]


@pytest.fixture
def vault_root(tmp_path: Path) -> Path:
    reset_config()
    build_synthetic_vault(
        tmp_path,
        n_docs=60,
        seed=29,
        edge_probability=0.3,
        pathologies=["cycle", "stem_collision"],
    )
    return tmp_path


class TestEngineParity:
    def test_rustworkx_is_active(self) -> None:
        # The dependency is declared; the fallback exists only for
        # platforms without the wheel, and this environment must exercise
        # the real engine.
        import rustworkx  # noqa: F401

    def test_betweenness_matches_networkx(self, vault_root: Path) -> None:
        graph = VaultGraph(vault_root, use_cache=False)
        g = graph.subgraph()

        seam = _betweenness_centrality(g)
        reference = nx.betweenness_centrality(g)

        assert seam.keys() == reference.keys()
        for node, expected in reference.items():
            assert seam[node] == pytest.approx(expected, abs=1e-12), node

    def test_feature_subgraph_matches_networkx(self, vault_root: Path) -> None:
        graph = VaultGraph(vault_root, use_cache=False)
        feature = graph.get_features()[0]
        g = graph.subgraph(feature=feature)

        seam = _betweenness_centrality(g)
        reference = nx.betweenness_centrality(g)

        assert seam.keys() == reference.keys()
        for node, expected in reference.items():
            assert seam[node] == pytest.approx(expected, abs=1e-12), node

    def test_metrics_scores_flow_through_seam(self, vault_root: Path) -> None:
        graph = VaultGraph(vault_root, use_cache=False)
        m = graph.metrics()
        assert len(m.betweenness_centrality) > 0
        for value in m.betweenness_centrality.values():
            assert 0.0 <= value <= 1.0
