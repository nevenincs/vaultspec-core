"""Bootstrap the FastMCP application for the vaultspec MCP server.

Constructs the ``FastMCP`` instance, registers the vault tool surface, and
provides the runtime entry boundary for ``vaultspec-mcp``. Supports both
root-CLI-injected context (via ``ctx.obj``) and standalone fallback
configuration via :func:`~vaultspec_core.config.get_config`.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import typer

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

from mcp.server.fastmcp import FastMCP

from vaultspec_core import __version__
from vaultspec_core.cli._app import make_app

from .tools import (
    register_document_tools,
    register_gateway_tools,
    register_orientation_tools,
    register_plan_tools,
)

logger = logging.getLogger(__name__)


def _build_instructions() -> str:
    """Compose the server ``instructions`` string naming the nine-tool surface.

    Names each first-class tool so a host that surfaces server instructions can
    orient an agent without a round-trip, and carries the tool-schema version
    (the package version per ADR Q8) as a third channel alongside the
    ``initialize`` implementation info and the ``status`` structured output, so
    the version survives the stateless protocol where ``initialize`` disappears.

    Returns:
        The assembled instructions string.
    """
    return (
        "Vaultspec-core MCP server (tool-schema version "
        f"{__version__}). Nine tools cover the vaultspec workflow. Hot path: "
        "'status' (project orientation and grounding traces), 'find' (document "
        "and feature discovery with blob hashes and resource links), 'create' "
        "(batch document scaffolding from templates), 'edit' (batch body-prose "
        "editing with optimistic-concurrency guards), 'plan_progress' (mark "
        "plan steps checked/unchecked), 'plan_edit' (add/insert/edit/remove "
        "plan steps), and 'check' (vault health checks with optional fix). "
        "Long tail: 'discover' searches the full verb catalog and returns "
        "parameter schemas on demand, and 'invoke' runs any cataloged verb "
        "against the installed binary. Prefer the hot tools; reach for "
        "discover/invoke for everything else. Mutations route through the "
        "owning verb logic, so canonical identifiers, frontmatter, and "
        "filenames are never hand-authored."
    )


# Plain-Click help to match the rest of the CLI (cli-presentation-uniformity
# ADR). ``no_args_is_help`` stays off so the no-argument invocation still runs
# the server via the ``invoke_without_command`` callback below.
app = make_app(help="Run the Vaultspec MCP server.", no_args_is_help=False)


@asynccontextmanager
async def _lifespan(_app: FastMCP) -> AsyncIterator[None]:
    """Unified server lifespan."""
    yield None


def create_server() -> FastMCP:
    """Create and configure the FastMCP server instance.

    Instantiates :class:`~mcp.server.fastmcp.FastMCP` and registers the vault
    tool surface via the domain ``register_*_tools`` functions in
    :mod:`vaultspec_core.mcp_server.tools`. Each tool handler runs in a copied
    :class:`contextvars.Context` so that per-request mutations do not leak
    between concurrent requests.

    Returns:
        Configured :class:`~mcp.server.fastmcp.FastMCP` instance ready to serve.
    """
    mcp = FastMCP(
        name="vaultspec-mcp",
        instructions=_build_instructions(),
        lifespan=_lifespan,
    )

    # Register the full nine-tool surface: find/create/edit (documents),
    # status/check (orientation), plan_progress/plan_edit (plan), and the
    # discover/invoke gateway. Every handler runs in a copied context for
    # concurrent-request isolation.
    register_document_tools(mcp)
    register_orientation_tools(mcp)
    register_plan_tools(mcp)
    register_gateway_tools(mcp)

    return mcp


def _serve(ctx_obj: dict | None = None) -> None:
    """Resolve runtime context, initialise paths, and start the MCP stdio server.

    Configures logging to stderr (to protect JSON-RPC on stdout), resolves
    ``root_dir`` from injected CLI context or fallback config, initialises
    core path globals via ``init_paths``, then calls ``mcp.run()``.

    Args:
        ctx_obj: Optional Typer context object injected by the root CLI app.
            Must contain ``"layout"`` and ``"target"`` keys when present.

    Raises:
        typer.Exit: If ``root_dir`` cannot be resolved in standalone mode.
    """
    from ..core.types import init_paths
    from ..logging_config import configure_logging

    # Ensure MCP uses stderr for everything to protect JSON-RPC on stdout
    configure_logging()

    # The layout and config may be injected by the root Typer app in cli.py
    if ctx_obj and "layout" in ctx_obj:
        root_dir = ctx_obj["target"]
    else:
        # Fallback if run standalone
        from ..config import get_config

        cfg = get_config()
        root_dir = cfg.target_dir
        if not root_dir:
            typer.echo("Error: Target directory not resolved.", err=True)
            raise typer.Exit(1)

    # Initialize core paths (TARGET_DIR, TEMPLATES_DIR, etc.)
    init_paths(root_dir)

    logger.info("Starting vaultspec-mcp server root=%s", root_dir)

    mcp = create_server()

    # FastMCP run() is synchronous, but we can call it here. On Windows the
    # default event loop has been the Proactor loop since Python 3.8, which the
    # MCP stdio transport requires, so no explicit policy override is needed.
    mcp.run()


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Typer callback entrypoint for vaultspec-mcp.

    Args:
        ctx: Typer context carrying the optional ``obj`` dict injected by
            the root CLI app (contains ``"layout"`` and ``"target"`` keys).
    """
    _serve(ctx.obj)


def run() -> None:
    """Console-script entrypoint for the packaged MCP executable."""
    app()


if __name__ == "__main__":
    run()
