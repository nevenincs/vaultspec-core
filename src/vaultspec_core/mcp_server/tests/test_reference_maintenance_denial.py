"""Installation reference maintenance cannot be granted by an MCP caller."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from mcp import Client
from mcp.server.mcpserver import MCPServer
from mcp.types import TextContent
from typer.testing import CliRunner

from vaultspec_core.cli import app
from vaultspec_core.cli.reference_surface import published_surface_path
from vaultspec_core.mcp_server.tools.gateway import register_gateway_tools

from .conftest import data_of, vault_root

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["vault_root"]

pytestmark = [pytest.mark.unit]


@pytest.mark.parametrize(
    ("verb", "arguments"),
    [
        ("spec reference generate", {}),
        (" spec   reference\tgenerate ", {"check": False}),
        ("spec reference snapshot", {"record": "-", "development": True}),
        ("spec reference snapshot", {"emit": True}),
    ],
)
async def test_gateway_refuses_maintenance_before_spawn(
    vault_root: Path,
    verb: str,
    arguments: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Even explicit development consent cannot authorize an MCP write."""

    async def unexpected_spawn(*args: object, **kwargs: object) -> None:
        pytest.fail("Reference maintenance spawned a child")

    monkeypatch.setattr(
        "vaultspec_core.mcp_server.tools.gateway._run_verb", unexpected_spawn
    )
    server = MCPServer(name="reference-maintenance-denial")
    register_gateway_tools(server)
    async with Client(server) as client:
        result = await client.call_tool(
            "invoke", {"verb": verb, "arguments": arguments}
        )
    assert result.is_error
    assert (
        "out of scope"
        in " ".join(
            item.text for item in result.content if isinstance(item, TextContent)
        ).lower()
    )


async def test_discovery_omits_installation_maintenance(vault_root: Path) -> None:
    """The catalog does not advertise the refused verbs."""
    server = MCPServer(name="reference-maintenance-discovery")
    register_gateway_tools(server)
    async with Client(server) as client:
        result = await client.call_tool("discover", {"query": "reference", "limit": 50})
    verbs = {entry["verb"] for entry in data_of(result)["verbs"]}
    assert "spec reference generate" not in verbs
    assert "spec reference snapshot" not in verbs


@pytest.mark.parametrize(
    "arguments",
    [
        ["generate"],
        ["snapshot", "--record", "-", "--development"],
    ],
)
def test_cli_rejects_gateway_writes(arguments: list[str]) -> None:
    """The child marker independently closes the write paths."""
    before = published_surface_path().read_bytes()
    result = CliRunner().invoke(
        app,
        ["spec", "reference", *arguments],
        input=before.decode(),
        env={"VAULTSPEC_MCP_GATEWAY_INVOCATION": "1"},
    )
    assert result.exit_code == 2
    assert "unavailable through MCP" in result.output
    assert published_surface_path().read_bytes() == before


def test_record_requires_explicit_development_context() -> None:
    """A valid input alone does not authorize changing installation files."""
    before = published_surface_path().read_bytes()
    result = CliRunner().invoke(
        app,
        ["spec", "reference", "snapshot", "--record", "-"],
        input=before.decode(),
    )
    assert result.exit_code == 2
    assert "requires --development" in result.output
    assert published_surface_path().read_bytes() == before


@pytest.mark.parametrize(
    "arguments",
    [
        ["snapshot"],
        ["snapshot", "--emit"],
        ["snapshot", "--verify", "-"],
        ["generate", "--check"],
    ],
)
def test_cli_read_only_modes_remain_available(arguments: list[str]) -> None:
    """The child guard only rejects modes that can write."""
    result = CliRunner().invoke(
        app,
        ["spec", "reference", *arguments],
        input=published_surface_path().read_text(encoding="utf-8"),
        env={"VAULTSPEC_MCP_GATEWAY_INVOCATION": "1"},
    )
    assert result.exit_code == 0, result.output
