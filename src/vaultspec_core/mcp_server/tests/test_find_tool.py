"""Tests for the ``find`` document-search limit contract.

These pin the documented behavior of the ``limit`` argument in search mode: a
single *global* cap applied to the type-ordered concatenation of results, not
a per-type quota. The regression guarded is a silent drift where ``limit``
starts meaning "per type" or the type ordering stops being honored. No mocks,
stubs, or skips: real documents are scaffolded through the ``create`` tool and
searched through the ``find`` tool on the real MCPServer.

The rest of the ``find`` query surface - the feature roll-ups, the ``feature``
and ``type`` filters, exec exclusion, and ``body`` - is pinned by the
``test_find_queries`` module against raw on-disk documents.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from mcp import Client

from vaultspec_core.mcp_server.app import create_server

from .conftest import data_of

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


async def _create(client: Client, documents: list[dict[str, Any]]) -> Any:
    result = await client.call_tool("create", {"documents": documents})
    return data_of(result)


async def test_find_limit_is_global_and_type_ordered(vault_root: Path) -> None:
    """``limit`` caps the concatenated result in type-list order, not per type.

    Two ``research`` and two ``reference`` documents exist; a search across
    ``[research, reference]`` with ``limit=2`` returns two ``research`` rows -
    the first type fills the global cap and crowds out ``reference`` - and
    ``limit=3`` returns both ``research`` rows plus one ``reference`` row.
    """
    mcp = create_server()
    async with Client(mcp) as client:
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
