"""Local type stub narrowing ``networkx.generators.ego``.

typeshed's bundled ``networkx`` stubs declare ``ego_graph`` without a return
annotation, so the ego subgraph reports as ``Unknown`` however precisely the
input graph is typed. This stub restates it with the graph type it actually
returns.

The module's complete ``__all__`` upstream is ``ego_graph`` alone, so
shadowing it costs the ``networkx`` namespace nothing. ``center`` and
``distance`` are omitted because no call site passes them; add them here
when one does.
"""

import networkx as nx

__all__ = ["ego_graph"]

def ego_graph(
    G: nx.DiGraph[str],
    n: str,
    radius: float = 1,
    *,
    undirected: bool = False,
) -> nx.DiGraph[str]: ...
