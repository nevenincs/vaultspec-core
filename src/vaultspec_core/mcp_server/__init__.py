"""MCPServer exposing vault tools over stdio transport.

Exports :func:`create_server` (factory returning a configured
:class:`mcp.server.mcpserver.MCPServer` with ``find`` and ``create`` tools) and
:func:`main` (entry point invoked by the ``vaultspec-core-mcp`` CLI script).
Depends on :mod:`vaultspec_core.core` for resource operations; consumed
directly by the ``vaultspec-core-mcp`` console-script entry point.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .app import create_server as create_server
    from .app import main as main

__all__ = [
    "create_server",
    "main",
]


def __getattr__(name: str) -> object:
    # Hosts launch the server as ``python -m vaultspec_core.mcp_server.app``,
    # which imports this package first; importing ``app`` here would load it
    # a second time beside ``__main__``.
    if name in __all__:
        from . import app

        return getattr(app, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
