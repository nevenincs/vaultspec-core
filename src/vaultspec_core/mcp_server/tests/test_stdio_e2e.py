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

from typing import TYPE_CHECKING, Any, cast

import pytest
from mcp.types import TextContent

from .conftest import (
    EXPECTED_TOOLS,
    READ_ONLY_TOOLS,
    data_of,
    run_in_fresh_workspace,
    stdio_session,
)

if TYPE_CHECKING:
    from pathlib import Path


async def _drive_session(project: Path) -> None:
    """Launch the real server over stdio and assert the full handshake path.

    Spawns ``python -m vaultspec_core.mcp_server.app`` as a child, rooted at a
    real installed vault, and exercises: the ``initialize`` handshake, the
    twelve-tool ``list_tools`` surface with output schemas, a structured ``status``
    call, the load-bearing ``invoke`` of a real long-tail verb, and denylist
    rejection - all over the actual JSON-RPC-on-stdio transport.
    """
    async with stdio_session(project) as session:
        init_result = await session.initialize()
        assert init_result.server_info.name == "vaultspec-core-mcp"

        listed = await session.list_tools()
        names = {tool.name for tool in listed.tools}
        assert names == EXPECTED_TOOLS, names
        for tool in listed.tools:
            assert tool.output_schema is not None, (
                f"{tool.name} advertises no outputSchema over the wire"
            )

        # status: read-only orientation returns structured content.
        status_payload = data_of(await session.call_tool("status", {}))
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
        invoke_payload = data_of(
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
    async with stdio_session(project, "--read-only") as session:
        await session.initialize()
        listed = await session.list_tools()
        by_name = {tool.name: tool for tool in listed.tools}
        assert set(by_name) == READ_ONLY_TOOLS, by_name
        assert "fix" not in by_name["check"].input_schema.get("properties", {})

        checked = data_of(await session.call_tool("check", {}))
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
    run_in_fresh_workspace(_drive_session, prefix="vsc-mcp-e2e-")


@pytest.mark.integration
def test_mcp_stdio_read_only_launch_omits_mutation_tools() -> None:
    """The real ``--read-only`` launch exposes only non-mutating tools."""
    run_in_fresh_workspace(_drive_read_only_session, prefix="vsc-mcp-read-only-")
