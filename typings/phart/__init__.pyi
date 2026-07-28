"""Minimal local type stub for the untyped third-party ``phart`` package.

``phart`` ships no ``py.typed`` marker, so basedpyright treats it as fully
untyped even though the installed source carries inline annotations. This
stub covers only the surface this codebase actually calls
(:class:`ASCIIRenderer`), mirroring ``phart.renderer.ASCIIRenderer``'s real
signature.
"""

from typing import Any

import networkx as nx

class ASCIIRenderer:
    graph: nx.Graph[Any]

    def __init__(
        self,
        graph: nx.Graph[Any],
        *,
        node_style: Any = ...,
        node_spacing: int = ...,
        layer_spacing: int = ...,
        use_ascii: bool | None = ...,
        custom_decorators: dict[str, tuple[str, str]] | None = ...,
        options: Any = ...,
    ) -> None: ...
    def render(self, print_config: bool | None = ...) -> str: ...
