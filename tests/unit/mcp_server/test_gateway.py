"""Tests for the discover/invoke gateway against the real installed binary.

Drives the gateway tools over the in-memory FastMCP session on a
:class:`WorkspaceFactory`-installed vault, with ``invoke`` spawning the real
``vaultspec-core`` module entry (``sys.executable -m vaultspec_core``) as an
argv-list subprocess - no mocks, stubs, or skips. Covers a read-only verb
returning parsed JSON, an unknown and a denylisted verb rejected before any
spawn, a non-zero exit folding stderr into the structured error payload,
reserved and unknown flag rejection, and the ``discover`` ranking order.
"""

from __future__ import annotations

from typing import Any

import pytest
from mcp.server.fastmcp import FastMCP
from mcp.shared.memory import create_connected_server_and_client_session

from vaultspec_core.mcp_server.tools.gateway import register_gateway_tools

from .conftest import data_of, vault_root  # noqa: F401 - re-exported fixture

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


def _gateway_server() -> FastMCP:
    """Build a FastMCP server exposing only the two gateway tools.

    Registering onto a local instance exercises the gateway handlers in
    isolation end-to-end through the same session transport; the full
    nine-tool ``create_server`` wiring is covered by the surface test.
    """
    mcp = FastMCP(name="vaultspec-mcp-gateway-test")
    register_gateway_tools(mcp)
    return mcp


def _error_text(result: Any) -> str:
    """Concatenate the text content of a ``CallToolResult`` for assertions."""
    parts = [str(c.text) for c in result.content if hasattr(c, "text")]
    return " ".join(parts).lower()


async def test_invoke_readonly_verb_returns_parsed_json(vault_root):  # noqa: F811
    """A ``--json``-supporting read-only verb returns parsed structured data."""
    mcp = _gateway_server()
    async with create_connected_server_and_client_session(mcp) as client:
        result = await client.call_tool("invoke", {"verb": "vault list"})
        payload = data_of(result)
        assert payload["ok"] is True
        assert payload["exit_code"] == 0
        assert payload["format"] == "json"
        # The parsed payload is the real ``vault list`` envelope, not raw text.
        assert payload["data"]["schema"].startswith("vaultspec.vault.list")
        assert payload["stdout"] is None
        assert payload["command"][0] == "vaultspec-core"


async def test_invoke_unknown_verb_rejected_before_spawn(vault_root):  # noqa: F811
    """An undeclared verb raises a protocol error and never spawns a process."""
    mcp = _gateway_server()
    async with create_connected_server_and_client_session(mcp) as client:
        result = await client.call_tool("invoke", {"verb": "totally bogus verb"})
        assert result.isError
        text = _error_text(result)
        assert "unknown verb" in text


async def test_invoke_denied_verb_rejected_before_spawn(vault_root):  # noqa: F811
    """Denylisted verbs are rejected before any spawn at the invoke boundary."""
    mcp = _gateway_server()
    async with create_connected_server_and_client_session(mcp) as client:
        for verb in ("uninstall", "vault feature index", "spec mcps add"):
            result = await client.call_tool("invoke", {"verb": verb})
            assert result.isError, verb
            text = _error_text(result)
            assert "denylist" in text or "out of scope" in text, verb


async def test_invoke_nonzero_exit_folds_stderr(vault_root):  # noqa: F811
    """A verb that runs and exits non-zero folds stderr into the error payload."""
    mcp = _gateway_server()
    async with create_connected_server_and_client_session(mcp) as client:
        # ``vault plan status`` requires a positional PATH; omitting it makes the
        # real binary exit non-zero with a usage error on stderr.
        result = await client.call_tool("invoke", {"verb": "vault plan status"})
        payload = data_of(result)
        assert payload["ok"] is False
        assert payload["exit_code"] != 0
        assert payload["error"]["kind"] == "nonzero_exit"
        assert payload["error"]["exit_code"] == payload["exit_code"]
        assert "missing argument" in payload["error"]["stderr"].lower()


async def test_invoke_reserved_flag_rejected(vault_root):  # noqa: F811
    """A caller cannot shadow the server-managed ``--json`` / ``--target``."""
    mcp = _gateway_server()
    async with create_connected_server_and_client_session(mcp) as client:
        result = await client.call_tool(
            "invoke", {"verb": "vault list", "arguments": {"json": True}}
        )
        assert result.isError
        text = _error_text(result)
        assert "reserved" in text


async def test_invoke_unknown_flag_rejected(vault_root):  # noqa: F811
    """An argument naming an undeclared flag is rejected before spawn."""
    mcp = _gateway_server()
    async with create_connected_server_and_client_session(mcp) as client:
        result = await client.call_tool(
            "invoke", {"verb": "vault list", "arguments": {"nonesuch": "x"}}
        )
        assert result.isError
        text = _error_text(result)
        assert "unknown flag" in text


async def test_invoke_value_flag_passed_through(vault_root):  # noqa: F811
    """A declared value flag reaches the binary as a discrete argv item."""
    mcp = _gateway_server()
    async with create_connected_server_and_client_session(mcp) as client:
        result = await client.call_tool(
            "invoke",
            {"verb": "vault list", "arguments": {"feature": "no-such-feature"}},
        )
        payload = data_of(result)
        assert payload["ok"] is True
        assert "--feature" in payload["command"]
        assert "no-such-feature" in payload["command"]


async def test_invoke_positional_verb_runs_end_to_end(vault_root):  # noqa: F811
    """A verb needing a positional operand is callable via ``positionals``.

    ``vault add <DOC_TYPE> --feature <tag>`` needs the document type as an
    ordered positional; the gateway must place it in the operand slot ahead of
    the ``--feature`` flag and the injected ``--json`` for the real binary to
    scaffold the document and exit clean.
    """
    mcp = _gateway_server()
    async with create_connected_server_and_client_session(mcp) as client:
        result = await client.call_tool(
            "invoke",
            {
                "verb": "vault add",
                "positionals": ["research"],
                "arguments": {"feature": "gateway-positional-probe"},
            },
        )
        payload = data_of(result)
        assert payload["ok"] is True, payload
        assert payload["exit_code"] == 0
        assert payload["format"] == "json"
        # The positional lands in the operand slot: right after the verb path
        # (which itself follows the injected --target) and before the flags.
        command = payload["command"]
        add_index = command.index("add")
        assert command[add_index - 1] == "vault"
        assert command[add_index + 1] == "research"
        feature_index = command.index("--feature")
        assert feature_index > add_index + 1
        # The verb really ran: a research document now exists for the feature.
        created = list(
            (vault_root / ".vault" / "research").glob(
                "*gateway-positional-probe*.md"
            )
        )
        assert created, "invoke did not scaffold the research document"


async def test_invoke_rejects_positional_for_argless_verb(vault_root):  # noqa: F811
    """A positional supplied to a verb that declares none is rejected pre-spawn."""
    mcp = _gateway_server()
    async with create_connected_server_and_client_session(mcp) as client:
        # ``vault stats`` declares no positional arguments; a stray operand
        # is refused by catalog validation before any process spawns.
        result = await client.call_tool(
            "invoke", {"verb": "vault stats", "positionals": ["stray"]}
        )
        assert result.isError
        text = _error_text(result)
        assert "no positional" in text


async def test_discover_returns_ranked_schemas(vault_root):  # noqa: F811
    """``discover`` ranks a known verb first and returns its parameter schema."""
    mcp = _gateway_server()
    async with create_connected_server_and_client_session(mcp) as client:
        result = await client.call_tool("discover", {"query": "list vault documents"})
        payload = data_of(result)
        assert payload["count"] >= 1
        verbs = payload["verbs"]
        assert "vault list" in {v["verb"] for v in verbs}
        # Ranking is non-increasing by score.
        scores = [v["score"] for v in verbs]
        assert scores == sorted(scores, reverse=True)
        # The ranked entry carries its full flag schema for on-demand loading.
        vault_list = next(v for v in verbs if v["verb"] == "vault list")
        assert vault_list["supports_json"] is True
        assert "--feature" in {f["name"] for f in vault_list["flags"]}


async def test_discover_excludes_denylisted_verbs(vault_root):  # noqa: F811
    """A denied verb never appears in discover results."""
    mcp = _gateway_server()
    async with create_connected_server_and_client_session(mcp) as client:
        result = await client.call_tool(
            "discover", {"query": "feature index generate", "limit": 50}
        )
        payload = data_of(result)
        assert "vault feature index" not in {v["verb"] for v in payload["verbs"]}
