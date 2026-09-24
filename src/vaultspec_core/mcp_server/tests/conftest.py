"""Shared fixtures for the MCP server tests.

Builds a real installed vault through the :class:`WorkspaceFactory` unified
fixture over a stdlib ``tempfile`` root (the repo ``tmp_path`` compat shim is
deliberately sidestepped), initialises the global path context, and exposes
a helper to unwrap a ``CallToolResult`` into its structured payload.  No
mocks, stubs, or skips: every test drives the real MCPServer, over the
in-memory session transport or, through :func:`stdio_session`, as a real
subprocess on stdio, against the real filesystem.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import sys
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, TextIO, cast

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent

from vaultspec_core.config import reset_config
from vaultspec_core.core.types import init_paths
from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory

if TYPE_CHECKING:
    from collections.abc import (
        AsyncGenerator,
        Callable,
        Coroutine,
        Iterator,
        Mapping,
    )

    from mcp.types import CallToolResult

    from vaultspec_core.testing.workspace_templates import (
        WorkspaceTemplates,
    )

pytestmark = [pytest.mark.unit]

#: The twelve tools the full surface advertises, and nothing else: ten hot
#: tools plus the ``discover`` / ``invoke`` gateway. Every surface test holds
#: the server against this one set, so a tool cannot join the surface in one
#: test's view and not another's.
EXPECTED_TOOLS = frozenset(
    {
        "status",
        "find",
        "search",
        "crossref",
        "create",
        "edit",
        "plan_progress",
        "plan_edit",
        "log",
        "check",
        "discover",
        "invoke",
    }
)

#: The non-mutating subset the ``--read-only`` launch advertises.
READ_ONLY_TOOLS = frozenset(
    {"status", "find", "search", "crossref", "check", "discover"}
)


def _build_installed_workspace(dest: Path) -> None:
    """Populate *dest* with a real, fully installed workspace."""
    dest.mkdir(parents=True)
    WorkspaceFactory(dest).install()


@pytest.fixture
def vault_root(workspace_templates: WorkspaceTemplates) -> Iterator[Path]:
    """Yield an installed vault root with the global path context set.

    The tree is a private copy of a session-scoped template rather than a fresh
    :class:`WorkspaceFactory` install per test: this fixture was the second
    largest consumer of fixture time in the suite, at 53 minutes over 78 uses,
    all of them building the identical tree. The copy is writable and torn down
    afterwards, so the create/edit cores still resolve real templates, scan a
    real vault, and write real files.

    The root is a stdlib ``tempfile`` directory rather than ``tmp_path`` for the
    reason the module docstring gives - the repo compat shim is deliberately
    sidestepped - and is resolved for the reason :class:`WorkspaceFactory`
    resolves its own root.
    """
    reset_config()
    root = Path(tempfile.mkdtemp(prefix="vsc-mcp-doc-")).resolve()
    try:
        workspace = workspace_templates.clone(
            "installed-workspace", root / "project", _build_installed_workspace
        )
        init_paths(workspace)
        yield workspace
    finally:
        reset_config()
        import shutil

        shutil.rmtree(root, ignore_errors=True)


def data_of(result: CallToolResult) -> Any:
    """Unwrap a ``CallToolResult`` into its structured payload.

    Asserts the call did not surface a protocol error, then returns the
    structured content (unwrapping MCPServer's ``{"result": ...}`` envelope
    when present).

    Args:
        result: The ``CallToolResult`` from an in-memory tool call.

    Returns:
        The structured Python payload the tool returned.
    """
    error_texts = [c.text for c in result.content if isinstance(c, TextContent)]
    assert not result.is_error, f"Tool returned error: {error_texts}"
    sc = result.structured_content
    if isinstance(sc, dict):
        # The MCP SDK declares ``structured_content`` as untyped ``Any``; at
        # runtime it is JSON, decoded by the SDK, so a dict payload always
        # has string keys (RFC 8259).
        payload = cast("dict[str, Any]", sc)
        if list(payload.keys()) == ["result"]:
            return payload["result"]
        return payload
    return sc


#: Overall ceiling for one stdio client session. Deliberately below the 60s
#: ``invoke`` subprocess timeout so a stdin-inheritance regression trips this
#: bound and fails fast rather than hanging CI to the per-call ceiling.
STDIO_SESSION_TIMEOUT = 45.0


@asynccontextmanager
async def _server_errlog() -> AsyncGenerator[TextIO]:
    """Yield a stderr for the server subprocess that has a real file descriptor.

    ``stdio_client`` defaults ``errlog`` to ``sys.stderr`` and hands it to
    ``subprocess``, which needs a descriptor to inherit. Under pytest's
    sys-level capture - which is what xdist workers run - ``sys.stderr`` is a
    Python object with no ``fileno()``, and the spawn dies with
    ``io.UnsupportedOperation`` before the server ever starts. The failure
    looks like a transport bug and is really the harness.

    ``sys.__stderr__`` is the interpreter's own stderr and keeps its
    descriptor whatever the capture mode, so the server's diagnostics still
    reach the terminal and the CI log. It is ``None`` only where the
    interpreter was started without one, and there the diagnostics have
    nowhere to go anyway.

    Async purely so it composes into the ``async with`` that opens the
    transport; nothing here awaits.
    """
    if sys.__stderr__ is not None:
        yield sys.__stderr__
        return
    with Path(os.devnull).open("w", encoding="utf-8") as sink:
        yield sink


@asynccontextmanager
async def stdio_session(
    project: Path,
    *server_args: str,
    environ: Mapping[str, str] | None = None,
) -> AsyncGenerator[ClientSession]:
    """Launch the real server over stdio, rooted at *project*, and yield a session.

    The child runs ``python -m vaultspec_core.mcp_server.app`` exactly as a
    host launches it, so the JSON-RPC transport is the process's own
    stdin/stdout pipe. The session is not yet initialised; the caller runs
    ``initialize`` and may assert on its result.

    Args:
        project: The installed workspace the server is rooted at.
        server_args: Extra server arguments, such as ``--read-only``.
        environ: The child's environment; ``None`` inherits this process's.
            The target directory is set on top of it either way.

    Yields:
        A client session over the child's stdio.
    """
    base = os.environ if environ is None else environ
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "vaultspec_core.mcp_server.app", *server_args],
        cwd=str(project),
        env={**base, "VAULTSPEC_TARGET_DIR": str(project)},
    )
    async with (
        _server_errlog() as errlog,
        stdio_client(params, errlog=errlog) as (read, write),
        ClientSession(read, write) as session,
    ):
        yield session


def run_in_fresh_workspace(
    driver: Callable[[Path], Coroutine[Any, Any, None]], *, prefix: str
) -> None:
    """Install a fresh workspace and run *driver* against it within the ceiling.

    For the stdio tests, which own their event loop: they run through
    :func:`asyncio.run` (the default Windows policy is the Proactor loop the
    stdio transport requires), so they need no async plugin marker and fail
    fast on :data:`STDIO_SESSION_TIMEOUT` rather than hanging.

    Args:
        driver: Drives one or more sessions against the workspace root.
        prefix: The temporary directory's name prefix.
    """
    reset_config()
    project = Path(tempfile.mkdtemp(prefix=prefix)).resolve()
    try:
        WorkspaceFactory(project).install()

        async def _runner() -> None:
            await asyncio.wait_for(driver(project), timeout=STDIO_SESSION_TIMEOUT)

        asyncio.run(_runner())
    finally:
        reset_config()
        shutil.rmtree(project, ignore_errors=True)
