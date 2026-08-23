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

#: Aggregate ceiling for the full nine-tool wire surface, in characters.
#:
#: This is a **ratchet, not a target**. The measured surface is 43,919 chars
#: (~12.7K tokens at the 3.46 chars/token measured for this codebase's JSON),
#: and every one of those tokens is re-sent on every turn of every
#: conversation before any work happens. The ceiling sits just above the
#: current measurement so the surface cannot grow, and it is meant to be
#: *lowered* as the envelope campaign lands - never raised.
#:
#: Doctrine target is 5K tokens (~17,300 chars). Getting there is mostly a
#: matter of not shipping developer documentation to the model: Pydantic
#: lifts each result model's full docstring - ``Attributes:`` blocks and
#: reST markup included - into ``output_schema.description``, and the tool
#: descriptions carry ``Returns:``/``Raises:`` prose plus a ``ctx``
#: parameter that appears in no input schema.
MAX_TOOL_DEFINITION_CHARS = 45_000

#: Aggregate ceiling for the read-only surface (four tools), same rules.
#: Measured at 20,131 chars.
MAX_READ_ONLY_TOOL_DEFINITION_CHARS = 21_000

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
    """Serialize one tool exactly as the MCP wire format sends it.

    This must mirror the protocol byte-for-byte, because the number it
    produces is the only thing standing between the surface and unchecked
    growth. Two properties matter and both were previously wrong:

    * ``output_schema`` is part of the wire ``Tool`` and is the *largest*
      component of most tools - ``status`` is 86% output schema. An earlier
      version of this helper omitted it and measured only 50% of the real
      surface (25% in read-only mode), so the guard passed while roughly
      22K chars grew entirely ungoverned.
    * The wire encoding is compact JSON. Serializing with ``indent=2``
      inflates the measurement with whitespace the protocol never sends,
      which flatters the covered half while the uncovered half is free.

    ``model_dump(exclude_none=True, by_alias=True)`` is the same dump the
    SDK performs, so this tracks the protocol automatically if the ``Tool``
    model gains fields.
    """
    return json.dumps(
        tool.model_dump(exclude_none=True, by_alias=True),
        separators=(",", ":"),
    )


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


def _tool_component_sizes(tool: MCPTool) -> tuple[int, int, int]:
    """Return the ``(description, input_schema, output_schema)`` char costs.

    Reported on failure so a regression names the component that grew rather
    than only the total - the three have very different remedies.
    """
    return (
        len(tool.description or ""),
        len(json.dumps(tool.input_schema or {}, separators=(",", ":"))),
        len(json.dumps(tool.output_schema or {}, separators=(",", ":"))),
    )


def _budget_failure_report(tools: list[MCPTool], total: int, ceiling: int) -> str:
    """Build the diagnostic shown when a surface exceeds its ceiling."""
    rows = sorted(
        (
            (
                tool.name,
                len(_serialize_tool_definition(tool)),
                *_tool_component_sizes(tool),
            )
            for tool in tools
        ),
        key=lambda row: row[1],
        reverse=True,
    )
    breakdown = "\n".join(
        f"  {name:16s} {size:6,}  (desc {desc:,} / in {sin:,} / out {sout:,})"
        for name, size, desc, sin, sout in rows
    )
    desc_total = sum(row[2] for row in rows)
    out_total = sum(row[4] for row in rows)
    return (
        f"Aggregate tool definition size ({total:,} chars, "
        f"~{total / 3.46:,.0f} tokens) exceeds budget of {ceiling:,} chars.\n"
        f"This surface is re-sent on EVERY turn of every conversation.\n"
        f"Per-tool breakdown (largest first):\n{breakdown}\n"
        f"Descriptions total {desc_total:,} chars; output schemas total "
        f"{out_total:,} chars.\n"
        "Raising the ceiling is not the fix - it is a ratchet. Trim prose "
        "the model cannot act on."
    )


async def test_tool_definitions_within_context_budget(
    mcp_server: MCPServer[None],
) -> None:
    """Aggregate serialized tool definitions must stay under the char budget."""
    tools = await mcp_server.list_tools()
    total = sum(len(_serialize_tool_definition(tool)) for tool in tools)

    if total > MAX_TOOL_DEFINITION_CHARS:
        pytest.fail(_budget_failure_report(tools, total, MAX_TOOL_DEFINITION_CHARS))


async def test_read_only_tool_definitions_within_context_budget(
    tmp_path: Path,
) -> None:
    """The read-only surface has its own ceiling and its own regressions.

    Read-only registers four of the nine tools, so a change that bloats a
    shared result model surfaces here at a different ratio than on the full
    surface. Guarding only the full surface let this one drift furthest -
    it was the least covered of the two.
    """
    reset_config()
    for dt in DocType:
        (tmp_path / ".vault" / dt.value).mkdir(parents=True)
    for subdir in ("templates", "agents", "rules", "skills"):
        (tmp_path / ".vaultspec" / subdir).mkdir(parents=True)
    init_paths(tmp_path)

    try:
        tools = await create_server(read_only=True).list_tools()
        total = sum(len(_serialize_tool_definition(tool)) for tool in tools)
        if total > MAX_READ_ONLY_TOOL_DEFINITION_CHARS:
            pytest.fail(
                _budget_failure_report(
                    tools, total, MAX_READ_ONLY_TOOL_DEFINITION_CHARS
                )
            )
    finally:
        reset_config()


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
