"""Local type stub narrowing ``networkx.classes.function``.

typeshed's bundled ``networkx`` stubs declare ``density`` without a return
annotation, so its value reports as ``Unknown`` and contaminates every
metric computed from it. This stub restates the one function this codebase
calls out of the module's forty-odd exports.

Unlike the other two ``networkx`` stubs here, this one is deliberately
partial, and safely so: typeshed re-exports this module into the
``networkx`` namespace with a *relative* import (``from .function import *``
in ``networkx/classes/__init__.pyi``), which resolves inside the typeshed
package and never reaches ``stubPath``. So ``nx.degree``, ``nx.subgraph``,
``nx.get_node_attributes`` and the rest keep their upstream declarations;
only a direct ``from networkx.classes.function import ...`` sees this file.
That is also why :mod:`vaultspec_core.graph.api` imports ``density`` by its
defining module rather than as ``nx.density`` - the namespace alias cannot
reach this stub. Widen this file when a second function from the module is
called directly.
"""

import networkx as nx

def density(G: nx.DiGraph[str]) -> float: ...
