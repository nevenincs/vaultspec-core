"""Local type stub narrowing ``networkx.readwrite.json_graph.node_link``.

Unlike the other packages under ``typings/``, ``networkx`` is not untyped:
typeshed ships stubs for it and basedpyright bundles them. Those stubs
declare ``node_link_data`` and ``node_link_graph`` without return
annotations, so every call reports as "partially unknown" no matter how
precisely the input graph is typed. This stub restates the two functions
with the return types they actually produce.

It shadows the upstream module rather than merging with it - a stub file on
``stubPath`` replaces its typeshed counterpart wholesale - so the surface
here is the module's complete ``__all__`` (``node_link_data``,
``node_link_graph``) and nothing is lost from the ``networkx`` namespace.
The parameters are narrowed to the keyword actually passed at the call
sites; widen them here when a new one is used, rather than reaching for an
ignore comment.
"""

from typing import Any

import networkx as nx

__all__ = ["node_link_data", "node_link_graph"]

def node_link_data(G: nx.DiGraph[str], *, edges: str = "edges") -> dict[str, Any]: ...
def node_link_graph(
    data: dict[str, Any],
    *,
    directed: bool = False,
    multigraph: bool = True,
    edges: str = "edges",
) -> nx.DiGraph[str]: ...
