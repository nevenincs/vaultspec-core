"""Runtime library for vaultspec-managed workspaces.

Provides the full stack from workspace resolution and resource sync through
vault document modelling, health checks, graph analysis, metrics, hook
execution, MCP server, and the user-facing CLI.

Subpackages:
    :mod:`vaultspec_core.config`: Runtime settings and workspace-layout
        resolution (:class:`~vaultspec_core.config.VaultSpecConfig`,
        :func:`~vaultspec_core.config.resolve_workspace`).
    :mod:`vaultspec_core.core`: Resource-management and sync engine  -
        agents, rules, skills, system, exceptions, dry-run, and I/O helpers.
    :mod:`vaultspec_core.vaultcore`: ``.vault/`` document kernel  - domain
        models, frontmatter parsing, wiki-link extraction, and query helpers.
    :mod:`vaultspec_core.builtins`: Bundled canonical resources seeded on
        ``vaultspec-core install``.
    :mod:`vaultspec_core.cli`: Typer CLI  - ``install``, ``uninstall``,
        ``sync``, ``vault``, and ``spec`` command groups.
    :mod:`vaultspec_core.graph`: Vault document relationship graph backed by
        ``networkx`` (:class:`~vaultspec_core.graph.VaultGraph`).
    :mod:`vaultspec_core.triggers`: Declarative lifecycle hook runtime for
        vault/spec-core events.
    :mod:`vaultspec_core.metrics`: Lightweight aggregate statistics over
        ``.vault/`` content (:class:`~vaultspec_core.metrics.VaultSummary`).
    :mod:`vaultspec_core.mcp_server`: MCPServer exposing vault and
        spec-core tool surfaces over JSON-RPC/stdio.
    :mod:`vaultspec_core.protocol`: Model-provider abstraction for prompt
        execution (Claude, Gemini).
"""

from typing import TYPE_CHECKING, Any

__all__ = ["__version__"]

if TYPE_CHECKING:
    # __getattr__ below resolves this at runtime; a static declaration is
    # what tells a type checker the name in __all__ genuinely exists, since
    # nothing assigns it at module level until first access.
    __version__: str


def _installed_version() -> str:
    """Return the installed distribution's version, or a development stand-in."""
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("vaultspec-core")
    except PackageNotFoundError:
        return "0.0.0.dev0"


def __getattr__(name: str) -> Any:
    """Resolve ``__version__`` on first access rather than at import.

    Reading the installed distribution's metadata costs more than the rest of
    this package's import put together, and the modules a spawned worker
    imports for the value vocabulary alone never ask for it. Resolving it
    lazily keeps importing any submodule cheap, while
    ``from vaultspec_core import __version__`` still works.
    """
    if name == "__version__":
        resolved = _installed_version()
        globals()[name] = resolved
        return resolved
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
