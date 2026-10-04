"""The full gateway cannot use resource names as filesystem paths."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from mcp import Client
from mcp.server.mcpserver import MCPServer

from vaultspec_core.mcp_server.tools.gateway import register_gateway_tools

from .conftest import data_of, vault_root

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["vault_root"]
pytestmark = [pytest.mark.unit]


async def test_gateway_refuses_absolute_skill_removal(vault_root: Path) -> None:
    victim = vault_root / "operator-owned"
    victim.mkdir()
    marker = victim / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    server = MCPServer(name="resource-containment")
    register_gateway_tools(server)
    async with Client(server) as client:
        result = await client.call_tool(
            "invoke",
            {
                "verb": "spec skills remove",
                "positionals": [str(victim)],
                "arguments": {"force": True},
            },
        )
    payload = data_of(result)
    assert payload["ok"] is False
    assert "Invalid resource name" in str(payload)
    assert marker.read_text(encoding="utf-8") == "keep"
