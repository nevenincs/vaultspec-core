"""Real-runtime tests for the explicit untyped NetworkX boundary."""

from __future__ import annotations

import pytest

from ..networkx_runtime import (
    density,
    directed_graph,
    ego_graph,
    is_directed_graph,
    node_link_data,
    node_link_graph,
)

pytestmark = [pytest.mark.unit]


def test_directed_graph_is_real_and_mutable() -> None:
    graph = directed_graph()
    graph.add_edge("a", "b", kind="body")

    assert is_directed_graph(graph)
    assert graph.edges["a", "b"]["kind"] == "body"


def test_node_link_round_trip_preserves_graph_content() -> None:
    graph = directed_graph()
    graph.add_edge("a", "b", kind="related")

    data = node_link_data(graph)
    restored = node_link_graph(data)

    assert set(restored.nodes()) == {"a", "b"}
    assert restored.edges["a", "b"]["kind"] == "related"


def test_ego_graph_respects_radius() -> None:
    graph = directed_graph()
    graph.add_edges_from([("a", "b"), ("b", "c")])

    ego = ego_graph(graph, "a", radius=1, undirected=True)

    assert set(ego.nodes()) == {"a", "b"}


def test_density_normalizes_networkx_numeric_edge_cases() -> None:
    empty = directed_graph()
    connected = directed_graph()
    connected.add_edge("a", "b")

    assert density(empty) == 0.0
    assert density(connected) == 0.5
