"""Tests for the ``find`` document-search limit contract.

These pin the documented behavior of the ``limit`` argument in search mode: a
single *global* cap applied to the type-ordered concatenation of results, not
a per-type quota. The regression guarded is a silent drift where ``limit``
starts meaning "per type" or the type ordering stops being honored. No mocks,
stubs, or skips: real documents are scaffolded through the ``create`` tool and
searched through the ``find`` tool on the real FastMCP server.
"""

from __future__ import annotations

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from vaultspec_core.mcp_server.app import create_server

from .conftest import data_of

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


async def _create(client, documents):
    result = await client.call_tool("create", {"documents": documents})
    return data_of(result)


async def test_find_limit_is_global_and_type_ordered(vault_root):
    """``limit`` caps the concatenated result in type-list order, not per type.

    Two ``research`` and two ``reference`` documents exist; a search across
    ``[research, reference]`` with ``limit=2`` returns two ``research`` rows -
    the first type fills the global cap and crowds out ``reference`` - and
    ``limit=3`` returns both ``research`` rows plus one ``reference`` row.
    """
    mcp = create_server()
    async with create_connected_server_and_client_session(mcp) as client:
        created = await _create(
            client,
            [
                {"feature": "find-alpha", "type": "research"},
                {"feature": "find-beta", "type": "research"},
                {"feature": "find-gamma", "type": "reference"},
                {"feature": "find-delta", "type": "reference"},
            ],
        )
        assert [item["status"] for item in created["items"]] == ["created"] * 4

        capped = data_of(
            await client.call_tool(
                "find", {"type": ["research", "reference"], "limit": 2}
            )
        )
        assert len(capped) == 2
        # The global cap is filled by the first type in the list order.
        assert {row["type"] for row in capped} == {"research"}

        spillover = data_of(
            await client.call_tool(
                "find", {"type": ["research", "reference"], "limit": 3}
            )
        )
        assert len(spillover) == 3
        types = [row["type"] for row in spillover]
        # Both research rows come first (type-list order), then one reference.
        assert types == ["research", "research", "reference"]
