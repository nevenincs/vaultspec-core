"""Bootstrap the MCPServer application for the vaultspec MCP server.

Constructs the ``MCPServer`` instance, registers the vault tool surface, and
provides the runtime entry boundary for ``vaultspec-mcp``. Supports both
root-CLI-injected context (via ``ctx.obj``) and standalone fallback
configuration via :func:`~vaultspec_core.config.get_config`.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Annotated, Any, override

import typer

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from mcp.server.context import CallNext, HandlerResult, ServerRequestContext

from mcp.server.extension import Extension
from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolRequestParams, CallToolResult, TextContent

from vaultspec_core import __version__
from vaultspec_core.cli._app import make_app

from .tools import (
    register_document_tools,
    register_exec_tools,
    register_gateway_tools,
    register_orientation_tools,
    register_plan_tools,
)

logger = logging.getLogger(__name__)


class _ReadOnlyCheckGuard(Extension):
    """Reject repair arguments that the SDK would otherwise ignore."""

    identifier = "io.vaultspec/read-only-check"

    @override
    async def intercept_tool_call(
        self,
        params: CallToolRequestParams,
        ctx: ServerRequestContext[Any, Any],
        call_next: CallNext,
    ) -> HandlerResult:
        if params.name == "check" and "fix" in (params.arguments or {}):
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text="read-only check does not accept the 'fix' argument",
                    )
                ],
                is_error=True,
            )
        return await call_next(ctx)


def _build_instructions(*, read_only: bool) -> str:
    """Compose the server ``instructions`` string for the selected surface.

    Names each first-class tool so a host that surfaces server instructions can
    orient an agent without a round-trip, and carries the tool-schema version
    (the package version per ADR Q8) as a third channel alongside the
    ``initialize`` implementation info and the ``status`` structured output, so
    the version survives the stateless protocol where ``initialize`` disappears.

    Returns:
        The assembled instructions string.
    """
    if read_only:
        return (
            "Vaultspec-core MCP server in read-only mode (tool-schema version "
            f"{__version__}). It exposes only 'status' (project orientation and "
            "grounding traces), 'find' (document and feature discovery with blob "
            "hashes and resource links), 'check' (vault health validation without "
            "repair), and 'discover' (read-only search of the verb catalog). "
            "Mutation tools and the invocation gateway are deliberately absent."
        )

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
async def _lifespan(_app: MCPServer[None]) -> AsyncGenerator[None]:
    """Unified server lifespan."""
    yield None


def create_server(*, read_only: bool = False) -> MCPServer[None]:
    """Create and configure the MCPServer instance.

    Instantiates :class:`~mcp.server.mcpserver.MCPServer` and registers the
    vault tool surface via the domain ``register_*_tools`` functions in
    :mod:`vaultspec_core.mcp_server.tools`. Each tool handler runs in a copied
    :class:`contextvars.Context` so that per-request mutations do not leak
    between concurrent requests.

    Args:
        read_only: Whether to expose only the non-mutating tool surface.

    Returns:
        Configured :class:`~mcp.server.mcpserver.MCPServer` ready to serve.
    """
    mcp = MCPServer(
        name="vaultspec-mcp",
        instructions=_build_instructions(read_only=read_only),
        lifespan=_lifespan,
        extensions=[_ReadOnlyCheckGuard()] if read_only else None,
    )

    # The restricted mode is a positive allowlist: only non-mutating handlers
    # are registered, so no write-capable tool reaches the advertised catalog.
    register_document_tools(mcp, include_mutations=not read_only)
    register_orientation_tools(mcp, include_fix=not read_only)
    if not read_only:
        register_plan_tools(mcp)
        register_exec_tools(mcp)
    register_gateway_tools(mcp, include_invoke=not read_only)

    return mcp


def _serve(
    ctx_obj: dict[str, Any] | None = None,
    parent_pid: int | None = None,
    read_only: bool = False,
) -> None:
    """Resolve runtime context, initialise paths, and start the MCP stdio server.

    Configures logging to stderr (to protect JSON-RPC on stdout), resolves
    ``root_dir`` from injected CLI context or fallback config, initialises
    core path globals via ``init_paths``, then calls ``mcp.run()``.

    Args:
        ctx_obj: Optional Typer context object injected by the root CLI app.
            Must contain ``"layout"`` and ``"target"`` keys when present.
        parent_pid: Optional explicit client PID the lifetime watchdog watches
            ahead of discovery.
        read_only: Whether to expose only the non-mutating tool surface.

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

    mcp = create_server(read_only=read_only)

    # Backstop for the stdio lifetime contract: stdin EOF can be defeated by
    # inherited pipe handles, so anchor shutdown to the client process itself
    # (pipe creator primary, ancestor chain fallback, POSIX reparent poll).
    # Fails open to EOF-only behavior when it cannot arm.
    from .watchdog import arm_client_watchdog

    if arm_client_watchdog(parent_pid=parent_pid):
        logger.debug("Client watchdog armed")
    else:
        logger.debug("Client watchdog not armed; relying on stdin EOF")

    # MCPServer run() is synchronous, but we can call it here. On Windows the
    # default event loop has been the Proactor loop since Python 3.8, which the
    # MCP stdio transport requires, so no explicit policy override is needed.
    mcp.run()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    parent_pid: Annotated[
        int | None,
        typer.Option(
            "--parent-pid",
            help=(
                "Explicit client PID for the stdio lifetime watchdog "
                "(watched in addition to the discovered client)"
            ),
        ),
    ] = None,
    read_only: Annotated[
        bool,
        typer.Option(
            "--read-only",
            help="Expose only non-mutating MCP tools.",
        ),
    ] = False,
) -> None:
    """Typer callback entrypoint for vaultspec-mcp.

    Args:
        ctx: Typer context carrying the optional ``obj`` dict injected by
            the root CLI app (contains ``"layout"`` and ``"target"`` keys).
        parent_pid: Optional explicit client PID forwarded to the lifetime
            watchdog.
        read_only: Whether to expose only the non-mutating tool surface.
    """
    _serve(ctx.obj, parent_pid=parent_pid, read_only=read_only)


def run() -> None:
    """Console-script entrypoint for the packaged MCP executable."""
    app()


if __name__ == "__main__":
    run()
