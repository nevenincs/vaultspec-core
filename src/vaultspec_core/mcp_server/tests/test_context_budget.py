"""Test that the MCP tool surface stays within a context budget.

Prevents tool definition bloat from consuming agent working context.
An MCPServer's tool definitions are serialized into every LLM
request  - keeping them compact is a hard requirement.

The budget is the concern here; the ``test_tool_surface`` module covers what
the same nine tools do end-to-end and the annotation matrix they declare.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.config import reset_config
from vaultspec_core.core.types import init_paths
from vaultspec_core.mcp_server.app import create_server
from vaultspec_core.vaultcore.models import DocType

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from mcp.server.mcpserver import MCPServer
    from mcp.types import Tool as MCPTool

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]

# Budget: the nine-tool surface serializes to ~21.5K chars today; the
# ceiling catches definition bloat without pinning every wording tweak.
MAX_TOOL_DEFINITION_CHARS = 26_000

# Maximum number of tools: the tiered surface is seven hot tools plus the
# discover/invoke gateway; growth beyond that needs a deliberate decision.
MAX_TOOL_COUNT = 9

# Exact expected tool surface.
EXPECTED_TOOLS = {
    "check",
    "create",
    "discover",
    "edit",
    "find",
    "invoke",
    "plan_edit",
    "plan_progress",
    "status",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _serialize_tool_definition(tool: MCPTool) -> str:
    """Serialize a single wire-format Tool definition to a JSON string."""
    tool_def = {
        "name": tool.name,
        "description": tool.description or "",
        "parameters": tool.input_schema or {},
    }
    return json.dumps(tool_def, indent=2)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mcp_server(tmp_path: Path) -> Generator[MCPServer[None]]:
    """Create a minimal workspace and build the MCP server."""
    reset_config()

    for dt in DocType:
        (tmp_path / ".vault" / dt.value).mkdir(parents=True)

    for subdir in ("templates", "agents", "rules", "skills"):
        (tmp_path / ".vaultspec" / subdir).mkdir(parents=True)

    init_paths(tmp_path)

    yield create_server()

    reset_config()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_tool_count_within_budget(mcp_server: MCPServer[None]) -> None:
    """The total number of registered tools must not exceed MAX_TOOL_COUNT."""
    tools = await mcp_server.list_tools()
    count = len(tools)
    assert count <= MAX_TOOL_COUNT, (
        f"Tool count {count} exceeds budget of {MAX_TOOL_COUNT}. "
        f"Registered tools: {sorted(tool.name for tool in tools)}"
    )


async def test_tool_surface_is_exact(mcp_server: MCPServer[None]) -> None:
    """The registered tool names must match EXPECTED_TOOLS exactly."""
    tools = await mcp_server.list_tools()
    actual = {tool.name for tool in tools}
    assert actual == EXPECTED_TOOLS, (
        f"Tool surface mismatch.\n"
        f"  Expected: {sorted(EXPECTED_TOOLS)}\n"
        f"  Actual:   {sorted(actual)}\n"
        f"  Extra:    {sorted(actual - EXPECTED_TOOLS)}\n"
        f"  Missing:  {sorted(EXPECTED_TOOLS - actual)}"
    )


async def test_tool_definitions_within_context_budget(
    mcp_server: MCPServer[None],
) -> None:
    """Aggregate serialized tool definitions must stay under the char budget."""
    tools = await mcp_server.list_tools()
    per_tool: list[tuple[str, int]] = []
    total = 0

    for tool in tools:
        serialized = _serialize_tool_definition(tool)
        size = len(serialized)
        per_tool.append((tool.name, size))
        total += size

    if total > MAX_TOOL_DEFINITION_CHARS:
        per_tool.sort(key=lambda t: t[1], reverse=True)
        breakdown = "\n".join(f"  {name}: {size:,} chars" for name, size in per_tool)
        pytest.fail(
            f"Aggregate tool definition size ({total:,} chars) exceeds budget "
            f"of {MAX_TOOL_DEFINITION_CHARS:,} chars.\n"
            f"Per-tool breakdown (largest first):\n{breakdown}"
        )


async def test_no_duplicate_tool_names(mcp_server: MCPServer[None]) -> None:
    """All registered tool names must be unique."""
    tools = await mcp_server.list_tools()
    names = [tool.name for tool in tools]
    seen: set[str] = set()
    duplicates: list[str] = []

    for name in names:
        if name in seen:
            duplicates.append(name)
        seen.add(name)

    assert not duplicates, f"Duplicate tool names found: {duplicates}"


async def test_all_tools_have_descriptions(mcp_server: MCPServer[None]) -> None:
    """Every registered tool must have a non-empty description."""
    tools = await mcp_server.list_tools()
    missing: list[str] = []

    for tool in tools:
        desc = (tool.description or "").strip()
        if not desc:
            missing.append(tool.name)

    assert not missing, (
        f"Tools missing descriptions: {missing}. "
        "Every tool must have a description so LLMs understand when to use it."
    )
