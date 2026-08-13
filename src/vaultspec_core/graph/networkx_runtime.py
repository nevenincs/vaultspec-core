"""Honest boundary around NetworkX's runtime-untyped graph objects.

NetworkX 3.6 graph classes do not implement ``__class_getitem__`` and therefore
have no runtime generic contract. This module contains that untyped third-party
boundary explicitly instead of projecting typeshed-only generics into the
owned graph domain.
"""

from __future__ import annotations

from typing import Any

import networkx as nx

__all__ = [
    "NetworkXGraph",
    "density",
    "directed_graph",
    "ego_graph",
    "is_directed_graph",
    "node_link_data",
    "node_link_graph",
]

type NetworkXGraph = Any
"""A real NetworkX graph whose third-party runtime surface is untyped."""


def _object_items(value: Any) -> list[tuple[object, object]]:
    """Materialize mapping items at the explicit untyped boundary."""
    return list(value.items())


def directed_graph() -> NetworkXGraph:
    """Return a real empty NetworkX directed graph."""
    graph: Any = nx.__dict__["DiGraph"]()
    return graph


def node_link_data(graph: NetworkXGraph) -> dict[str, Any]:
    """Serialize *graph* and validate NetworkX's untyped return shape."""
    from networkx.readwrite import json_graph

    value: Any = json_graph.__dict__["node_link_data"](graph, edges="edges")
    if not isinstance(value, dict):
        raise TypeError("networkx.node_link_data returned a non-dict value")
    items = _object_items(value)
    if not all(isinstance(key, str) for key, _item in items):
        raise TypeError("networkx.node_link_data returned a non-string key")
    return {key: item for key, item in items if isinstance(key, str)}


def node_link_graph(data: dict[str, Any]) -> NetworkXGraph:
    """Reconstruct a directed graph and validate NetworkX's runtime result."""
    from networkx.readwrite import json_graph

    value: Any = json_graph.__dict__["node_link_graph"](
        data,
        directed=True,
        multigraph=False,
        edges="edges",
    )
    if not is_directed_graph(value):
        raise TypeError("networkx.node_link_graph returned a non-DiGraph value")
    return value


def ego_graph(
    graph: NetworkXGraph,
    node: str,
    *,
    radius: int,
    undirected: bool,
) -> NetworkXGraph:
    """Build an ego graph and validate NetworkX's runtime result."""
    value: Any = nx.__dict__["ego_graph"](
        graph,
        node,
        radius=radius,
        undirected=undirected,
    )
    if not is_directed_graph(value):
        raise TypeError("networkx.ego_graph returned a non-DiGraph value")
    return value


def density(graph: NetworkXGraph) -> float:
    """Return graph density after validating NetworkX's numeric result."""
    value: Any = nx.__dict__["density"](graph)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("networkx.density returned a non-numeric value")
    return float(value)


def is_directed_graph(value: object) -> bool:
    """Return whether *value* is a real NetworkX directed graph."""
    graph_type: Any = nx.__dict__["DiGraph"]
    return isinstance(value, graph_type)
