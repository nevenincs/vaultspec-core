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
from typing import Any, cast

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult, TextContent

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

_READ_ONLY_TOOLS = frozenset({"status", "find", "check", "discover"})

#: Overall client-session ceiling. Deliberately below the 60s ``invoke``
#: subprocess timeout so a stdin-inheritance regression trips this bound and
#: fails fast rather than hanging CI to the per-call ceiling.
_SESSION_TIMEOUT = 45.0


def _unwrap(result: CallToolResult) -> Any:
    """Return a ``call_tool`` result's structured payload, error-checked.

    Asserts the call did not surface a protocol error, then returns the
    structured content, unwrapping MCPServer's ``{"result": ...}`` envelope when
    present (mirroring the in-memory suite's ``data_of`` helper).
    """
    error_texts = [c.text for c in result.content if isinstance(c, TextContent)]
    assert not result.is_error, f"tool returned error: {error_texts}"
    sc = result.structured_content
    if isinstance(sc, dict):
        # MCPServer's envelope is a JSON object; cast narrows away the
        # Unknown key/value types isinstance leaves on an ``Any``-typed
        # field.
        obj = cast("dict[str, Any]", sc)
        if list(obj.keys()) == ["result"]:
            return obj["result"]
        return obj
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
        assert init_result.server_info.name == "vaultspec-mcp"

        listed = await session.list_tools()
        names = {tool.name for tool in listed.tools}
        assert names == _EXPECTED_TOOLS, names
        for tool in listed.tools:
            assert tool.output_schema is not None, (
                f"{tool.name} advertises no outputSchema over the wire"
            )

        # status: read-only orientation returns structured content.
        status_payload = _unwrap(await session.call_tool("status", {}))
        assert isinstance(status_payload, dict)
        # Both tools declare an object output schema (asserted above), so
        # their structured payload is always a JSON object at runtime; cast
        # narrows away the Unknown key/value types isinstance leaves on an
        # ``Any``-typed value.
        status_dict = cast("dict[str, Any]", status_payload)
        assert status_dict.get("kind") == "rollup"

        # invoke a real long-tail verb: THIS is the guard. Without
        # stdin=DEVNULL in the invoke subprocess the child inherits the live
        # transport pipe and blocks, so this call never returns and the 45s
        # session ceiling trips instead of ``ok`` coming back.
        invoke_payload = _unwrap(
            await session.call_tool("invoke", {"verb": "vault list"})
        )
        assert isinstance(invoke_payload, dict)
        invoke_dict = cast("dict[str, Any]", invoke_payload)
        assert invoke_dict["ok"] is True, invoke_dict
        assert invoke_dict["exit_code"] == 0, invoke_dict
        assert invoke_dict["command"][0] == "vaultspec-core"

        # invoke of a denylisted verb is rejected as a protocol error.
        denied = await session.call_tool("invoke", {"verb": "uninstall"})
        assert denied.is_error
        denied_text = " ".join(
            str(c.text) for c in denied.content if isinstance(c, TextContent)
        ).lower()
        assert "denylist" in denied_text or "out of scope" in denied_text


async def _drive_read_only_session(project: Path) -> None:
    """Launch the real read-only server and prove its wire-visible surface."""
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "vaultspec_core.mcp_server.app", "--read-only"],
        cwd=str(project),
        env={**os.environ, "VAULTSPEC_TARGET_DIR": str(project)},
    )

    async with (
        stdio_client(params) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        listed = await session.list_tools()
        by_name = {tool.name: tool for tool in listed.tools}
        assert set(by_name) == _READ_ONLY_TOOLS, by_name
        assert "fix" not in by_name["check"].input_schema.get("properties", {})

        checked = _unwrap(await session.call_tool("check", {}))
        assert isinstance(checked, dict)
        check_dict = cast("dict[str, Any]", checked)
        assert check_dict["fixed"] is False

        rejected_repair = await session.call_tool("check", {"fix": True})
        assert rejected_repair.is_error


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
    project = Path(tempfile.mkdtemp(prefix="vsc-mcp-e2e-")).resolve()
    try:
        WorkspaceFactory(project).install()

        async def _runner() -> None:
            await asyncio.wait_for(_drive_session(project), timeout=_SESSION_TIMEOUT)

        asyncio.run(_runner())
    finally:
        reset_config()
        shutil.rmtree(project, ignore_errors=True)


@pytest.mark.integration
def test_mcp_stdio_read_only_launch_omits_mutation_tools() -> None:
    """The real ``--read-only`` launch exposes only non-mutating tools."""
    reset_config()
    project = Path(tempfile.mkdtemp(prefix="vsc-mcp-read-only-")).resolve()
    try:
        WorkspaceFactory(project).install()

        async def _runner() -> None:
            await asyncio.wait_for(
                _drive_read_only_session(project), timeout=_SESSION_TIMEOUT
            )

        asyncio.run(_runner())
    finally:
        reset_config()
        shutil.rmtree(project, ignore_errors=True)
