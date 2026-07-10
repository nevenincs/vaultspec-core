"""Live end-to-end regression guard for the MCP server over real stdio.

Every real agent host launches this server over stdio: the JSON-RPC transport
*is* the process's own stdin/stdout pipe. This test reproduces that exact wiring
- it spawns the actual server module as a subprocess through the ``mcp`` SDK's
``stdio_client`` and drives it with a real :class:`~mcp.ClientSession`, with no
mocks, stubs, or skips - so a whole class of transport bugs the in-memory
session transport cannot see is caught here.

The load-bearing assertion is the ``invoke`` of a real long-tail verb. ``invoke``
subprocesses the installed binary; if that child is spawned without
``stdin=subprocess.DEVNULL`` it inherits the server's stdin, which is the live
JSON-RPC transport pipe, and blocks reading it - the verb never returns and the
call hangs to its 60s ceiling while the protocol stream is corrupted. The
in-memory unit transport never exercises a real stdin, so only this end-to-end
path guards the fix. The whole session is wrapped in a hard 45s ceiling, well
under the 60s ``invoke`` timeout, so a regression fails fast instead of hanging
the suite.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from vaultspec_core.config import reset_config
from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory

#: The nine tools the redesigned surface must advertise over the wire.
_EXPECTED_TOOLS = frozenset(
    {
        "status",
        "find",
        "create",
        "edit",
        "plan_progress",
        "plan_edit",
        "check",
        "discover",
        "invoke",
    }
)

#: Overall client-session ceiling. Deliberately below the 60s ``invoke``
#: subprocess timeout so a stdin-inheritance regression trips this bound and
#: fails fast rather than hanging CI to the per-call ceiling.
_SESSION_TIMEOUT = 45.0


def _unwrap(result: Any) -> Any:
    """Return a ``call_tool`` result's structured payload, error-checked.

    Asserts the call did not surface a protocol error, then returns the
    structured content, unwrapping FastMCP's ``{"result": ...}`` envelope when
    present (mirroring the in-memory suite's ``data_of`` helper).
    """
    error_texts = [c.text for c in result.content if hasattr(c, "text")]
    assert not result.isError, f"tool returned error: {error_texts}"
    sc = result.structuredContent
    if isinstance(sc, dict) and list(sc.keys()) == ["result"]:
        return sc["result"]
    return sc


async def _drive_session(project: Path) -> None:
    """Launch the real server over stdio and assert the full handshake path.

    Spawns ``python -m vaultspec_core.mcp_server.app`` as a child, rooted at a
    real installed vault, and exercises: the ``initialize`` handshake, the
    nine-tool ``list_tools`` surface with output schemas, a structured ``status``
    call, the load-bearing ``invoke`` of a real long-tail verb, and denylist
    rejection - all over the actual JSON-RPC-on-stdio transport.
    """
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "vaultspec_core.mcp_server.app"],
        cwd=str(project),
        env={**os.environ, "VAULTSPEC_TARGET_DIR": str(project)},
    )

    async with (
        stdio_client(params) as (read, write),
        ClientSession(read, write) as session,
    ):
        init_result = await session.initialize()
        assert init_result.serverInfo.name == "vaultspec-mcp"

        listed = await session.list_tools()
        names = {tool.name for tool in listed.tools}
        assert names == _EXPECTED_TOOLS, names
        for tool in listed.tools:
            assert tool.outputSchema is not None, (
                f"{tool.name} advertises no outputSchema over the wire"
            )

        # status: read-only orientation returns structured content.
        status_payload = _unwrap(await session.call_tool("status", {}))
        assert isinstance(status_payload, dict)
        assert status_payload.get("kind") == "rollup"

        # invoke a real long-tail verb: THIS is the guard. Without
        # stdin=DEVNULL in the invoke subprocess the child inherits the live
        # transport pipe and blocks, so this call never returns and the 45s
        # session ceiling trips instead of ``ok`` coming back.
        invoke_payload = _unwrap(
            await session.call_tool("invoke", {"verb": "vault list"})
        )
        assert invoke_payload["ok"] is True, invoke_payload
        assert invoke_payload["exit_code"] == 0, invoke_payload
        assert invoke_payload["command"][0] == "vaultspec-core"

        # invoke of a denylisted verb is rejected as a protocol error.
        denied = await session.call_tool("invoke", {"verb": "uninstall"})
        assert denied.isError
        denied_text = " ".join(
            str(c.text) for c in denied.content if hasattr(c, "text")
        ).lower()
        assert "denylist" in denied_text or "out of scope" in denied_text


@pytest.mark.integration
def test_mcp_stdio_end_to_end_invoke_does_not_inherit_transport_stdin() -> None:
    """The server serves a full session over real stdio without stdin hangs.

    Regression guard: ``invoke`` must spawn its verb subprocess with
    ``stdin=subprocess.DEVNULL`` so the child never inherits the server's
    JSON-RPC-on-stdio transport pipe. Reverting that fix makes the ``invoke``
    call block on the inherited pipe until the 60s ceiling; the 45s session
    bound below turns that hang into a fast, deterministic failure.

    Driven with :func:`asyncio.run` (the default Windows event-loop policy is
    the Proactor loop the stdio transport requires) so the test needs no async
    plugin marker and fails fast on the hard timeout.
    """
    reset_config()
    project = Path(tempfile.mkdtemp(prefix="vsc-mcp-e2e-"))
    try:
        WorkspaceFactory(project).install()

        async def _runner() -> None:
            await asyncio.wait_for(_drive_session(project), timeout=_SESSION_TIMEOUT)

        asyncio.run(_runner())
    finally:
        reset_config()
        shutil.rmtree(project, ignore_errors=True)
