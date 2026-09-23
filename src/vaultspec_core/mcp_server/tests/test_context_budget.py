"""Test that the MCP tool surface stays within a context budget.

Prevents tool definition bloat from consuming agent working context.
An MCPServer's tool definitions are serialized into every LLM
request  - keeping them compact is a hard requirement.

The budget is the concern here; the ``test_tool_surface`` module covers what
the same eleven tools do end-to-end and the annotation matrix they declare.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

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

#: Aggregate ceiling for the full eleven-tool wire surface, in characters.
#:
#: This is a **ratchet, not a target**. The measured surface is 43,919 chars
#: (~5.4K tokens at ``ENVELOPE_BYTES_PER_TOKEN``, measured for this JSON),
#: and every one of those tokens is re-sent on every turn of every
#: conversation before any work happens. The ceiling sits just above the
#: current measurement so the surface cannot grow, and it is meant to be
#: *lowered* as the envelope campaign lands - never raised.
#:
#: Doctrine target is 5K tokens (~17,300 chars); the surface now sits just
#: above it. What remains is structure, not prose. Getting here was mostly a
#: matter of not shipping developer documentation to the model: Pydantic
#: lifts each result model's full docstring - ``Attributes:`` blocks and
#: reST markup included - into ``output_schema.description``, and the tool
#: descriptions carry ``Returns:``/``Raises:`` prose plus a ``ctx``
#: parameter that appears in no input schema.
#:
#: Raised once, by the size of the tenth tool, when ``log`` (the execution
#: ledger writer) joined the surface: one verb per artifact was the decision,
#: and a ledger row logged through ``invoke`` would cost a host confirmation
#: on every Step. Measured at 20,0xx chars with ``log`` at ~1.1K.
#:
#: Raised a second time, from 20,200, when hosted vault search joined the
#: surface as its ninth hot tool: a first-class tool rather than a gateway
#: verb, because ``invoke`` costs a host confirmation on every call. Measured
#: 20,199 before and 23,853 after (+3,654). ``search`` itself is 3,261
#: (description 582, input 727, output 1,799). ``status`` grew 315 for its
#: ``hosted_search`` field. ``find`` grew 78: its feature, date and type
#: filters now share one declaration with ``search``, which lists the record
#: types and describes each filter. The ceiling keeps a margin of 47.
#:
#: Raised a third time, from 23,900, by exactly the parameter documentation
#: the model had never received. The ``ctx`` trimming in ``tool_description``
#: matched arguments at a fixed indent that ``inspect.getdoc`` dedents away,
#: so it removed every argument documented after ``ctx``; the ``Args:``
#: guidance is what a caller acts on, which is the prose this ratchet exists
#: to keep. Measured 23,895 before the fix and 26,375 after (+2,480): invoke
#: +711, find +572, log +392, search +167, discover +139, plan_edit +130,
#: status +123, plan_progress +118, create +66, edit +62. Margin of 5.
#:
#: Lowered from 26,380 when ``search`` gained its typed ``next_step`` and
#: ``verdict``: the result models of ``search``, ``status`` and ``check``
#: stopped shipping property defaults, which describe input a result never
#: takes, and enum fields of dataclass shapes ship as their values alone.
#: Measured 26,375 before and 26,289 after (-86). Margin of 6.
#:
#: Lowered from 26,295 when ``status`` gained the ``companion`` record the
#: CLI already carried, so both status surfaces carry the same discovery
#: keys. The record alone measured +439. Result schemas paid for it: an
#: optional result key, omitted rather than sent null, stopped publishing a
#: null branch, and a key that is sent null spells it as a type list.
#: Measured 26,289 before, 25,643 with the schema change alone and 26,107
#: with the record (-182). Margin of 8.
#:
#: Held at 26,115 when ``log`` took ``verify`` as a list, as the CLI
#: repeats ``--verify``. The array schema cost 27; trimmed ``log``
#: parameter prose paid 23 of it. Measured 26,107 before and 26,111
#: after (+4). Margin of 4.
MAX_TOOL_DEFINITION_CHARS = 26_115

#: Aggregate ceiling for the read-only surface (five tools), same rules.
#: Measured at 9,194 chars. Raised from 9,500 by the same three changes, which
#: all reach this surface, since ``search`` is read-only: measured 9,446
#: before and 13,100 after (+3,654), with a margin of 50. Raised again from
#: 13,150 by the restored parameter documentation above: measured 13,142
#: before and 14,143 after (+1,001: find, search, discover and status), with
#: a margin of 8. Lowered from 14,151 by the same change as the full
#: surface: measured 14,143 before and 14,057 after (-86), margin of 8.
#: Lowered from 14,065 by the same ``companion`` record and schema change:
#: measured 14,057 before, 13,411 with the schema change alone and 13,875
#: with the record (-182), margin of 8.
MAX_READ_ONLY_TOOL_DEFINITION_CHARS = 13_883

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
    tokens = total / ENVELOPE_BYTES_PER_TOKEN
    return (
        f"Aggregate tool definition size ({total:,} chars, "
        f"~{tokens:,.0f} tokens) exceeds budget of {ceiling:,} chars.\n"
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

    Read-only registers five of the eleven tools, so a change that bloats a
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
