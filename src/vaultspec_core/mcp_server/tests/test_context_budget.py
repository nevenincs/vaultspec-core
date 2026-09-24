"""Test that the MCP tool surface stays within a context budget.

Prevents tool definition bloat from consuming agent working context.
An MCPServer's tool definitions are serialized into every LLM
request  - keeping them compact is a hard requirement.

The budget is the concern here; the ``test_tool_surface`` module covers what
the same eleven tools do end-to-end and the annotation matrix they declare.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

import pytest

from vaultspec_core.config import reset_config
from vaultspec_core.core.types import init_paths
from vaultspec_core.mcp_server.app import create_server
from vaultspec_core.search.tests.reply_budget import ENVELOPE_BYTES_PER_TOKEN
from vaultspec_core.vaultcore.models import DocType

from .conftest import EXPECTED_TOOLS

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from mcp.server.mcpserver import MCPServer
    from mcp.types import Tool as MCPTool

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]

#: Each tool's ceiling, in wire characters: description, input schema and
#: output schema serialised as the protocol sends them.
#:
#: Each tool owns its budget, and budgets move down as work lands, never up. A
#: new tool, or growth in one, changes its own entry, where review sees it.
#: The surface ceilings are the sums below, not numbers of their own. Doctrine
#: target for the whole surface: 5,000 tokens, about 17,300 characters.
TOOL_BUDGETS: dict[str, int] = {
    "status": 3_470,
    "search": 2_860,
    "find": 2_370,
    "create": 1_690,
    "invoke": 1_610,
    "plan_edit": 1_590,
    "plan_progress": 1_520,
    "edit": 1_510,
    "discover": 1_450,
    "check": 1_300,
    "log": 1_210,
}

# Maximum number of tools: the tiered surface is nine hot tools plus the
# discover/invoke gateway; growth beyond that needs a deliberate decision.
# Raised from 10 by exactly one, for ``search``, the ninth hot tool.
MAX_TOOL_COUNT = 11


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


def _init_workspace(root: Path) -> None:
    """Lay out the minimal workspace a server registers its tools against."""
    reset_config()
    for dt in DocType:
        (root / ".vault" / dt.value).mkdir(parents=True)
    for subdir in ("templates", "agents", "rules", "skills"):
        (root / ".vaultspec" / subdir).mkdir(parents=True)
    init_paths(root)


@pytest.fixture()
def mcp_server(tmp_path: Path) -> Generator[MCPServer[None]]:
    """Create a minimal workspace and build the full MCP server."""
    _init_workspace(tmp_path)
    yield create_server()
    reset_config()


@pytest.fixture(params=[False, True], ids=["full", "read-only"])
def surface(
    request: pytest.FixtureRequest, tmp_path: Path
) -> Generator[MCPServer[None]]:
    """Build the server on each surface: all eleven tools, and read-only's five.

    Read-only registers a subset, and ``check`` without its repair argument,
    so a change that bloats a shared result model surfaces there at a
    different ratio than on the full surface.
    """
    _init_workspace(tmp_path)
    yield create_server(read_only=cast("bool", request.param))
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
    """Build the diagnostic shown when a surface or a tool exceeds its budget."""
    rows = sorted(
        (
            (
                tool.name,
                len(_serialize_tool_definition(tool)),
                TOOL_BUDGETS.get(tool.name, 0),
                *_tool_component_sizes(tool),
            )
            for tool in tools
        ),
        key=lambda row: row[1],
        reverse=True,
    )
    breakdown = "\n".join(
        f"  {name:16s} {size:6,} of {budget:6,}"
        f"  (desc {desc:,} / in {sin:,} / out {sout:,})"
        for name, size, budget, desc, sin, sout in rows
    )
    desc_total = sum(row[3] for row in rows)
    out_total = sum(row[5] for row in rows)
    tokens = total / ENVELOPE_BYTES_PER_TOKEN
    return (
        f"Tool definitions total {total:,} chars (~{tokens:,.0f} tokens) "
        f"against a surface budget of {ceiling:,} chars.\n"
        f"This surface is re-sent on EVERY turn of every conversation.\n"
        f"Per-tool size against budget (largest first):\n{breakdown}\n"
        f"Descriptions total {desc_total:,} chars; output schemas total "
        f"{out_total:,} chars.\n"
        "Raising a budget is not the fix - budgets move down. Trim what the "
        "model cannot act on; a new tool or deliberate growth changes its own "
        "entry in TOOL_BUDGETS."
    )


async def test_every_tool_has_a_budget(mcp_server: MCPServer[None]) -> None:
    """A registered tool without its own budget entry is ungoverned."""
    names = {tool.name for tool in await mcp_server.list_tools()}
    missing = sorted(names - TOOL_BUDGETS.keys())
    assert not missing, f"Tools without an entry in TOOL_BUDGETS: {missing}"


async def test_every_budget_names_a_tool(mcp_server: MCPServer[None]) -> None:
    """A budget for a tool that does not exist inflates the surface ceiling."""
    names = {tool.name for tool in await mcp_server.list_tools()}
    stale = sorted(TOOL_BUDGETS.keys() - names)
    assert not stale, f"TOOL_BUDGETS entries for tools that do not exist: {stale}"


async def test_each_tool_within_its_budget(surface: MCPServer[None]) -> None:
    """Every tool stays under its own ceiling, named with its components."""
    tools = await surface.list_tools()
    over: list[str] = []
    for tool in tools:
        size = len(_serialize_tool_definition(tool))
        budget = TOOL_BUDGETS.get(tool.name, 0)
        if size > budget:
            desc, sin, sout = _tool_component_sizes(tool)
            over.append(
                f"{tool.name}: {size:,} chars against its budget of {budget:,} "
                f"(desc {desc:,} / in {sin:,} / out {sout:,})"
            )
    if over:
        total = sum(len(_serialize_tool_definition(tool)) for tool in tools)
        ceiling = sum(TOOL_BUDGETS.get(tool.name, 0) for tool in tools)
        report = _budget_failure_report(tools, total, ceiling)
        pytest.fail("\n".join([*over, report]))


async def test_surface_within_its_budget(surface: MCPServer[None]) -> None:
    """The surface stays under the sum of its tools' budgets."""
    tools = await surface.list_tools()
    total = sum(len(_serialize_tool_definition(tool)) for tool in tools)
    ceiling = sum(TOOL_BUDGETS.get(tool.name, 0) for tool in tools)
    if total > ceiling:
        pytest.fail(_budget_failure_report(tools, total, ceiling))


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
