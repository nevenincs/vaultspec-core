"""MCP find excludes linked bodies and URIs, including after a listing."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from mcp import Client

from vaultspec_core.mcp_server.app import create_server
from vaultspec_core.vaultcore import query
from vaultspec_core.vaultcore.blob_hash import git_blob_oid

from .conftest import data_of
from .test_find_queries import _write_doc

if TYPE_CHECKING:
    from pathlib import Path

    from vaultspec_core.graph import VaultGraph
    from vaultspec_core.vaultcore.query_listing import VaultDocument

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


@pytest.mark.parametrize("after_listing", [False, True])
async def test_find_never_returns_linked_content_or_resource_uri(
    vault_root: Path, monkeypatch: pytest.MonkeyPatch, after_listing: bool
) -> None:
    safe = _write_doc(vault_root, "adr", "corpus-safe", "2026-01-01", body="Public.")
    leak = _write_doc(vault_root, "adr", "corpus-leak", "2026-01-01")
    outside = vault_root.parent / "private.txt"
    outside.write_text("PRIVATE-SECRET", encoding="utf-8")

    def replace_with_link() -> None:
        leak.unlink()
        leak.symlink_to(outside)

    if after_listing:
        original_listing = query.list_documents

        def listing_then_replace(
            root_dir: Path,
            *,
            doc_type: str | None = None,
            feature: str | None = None,
            date: str | None = None,
            graph: VaultGraph | None = None,
        ) -> list[VaultDocument]:
            docs = original_listing(
                root_dir, doc_type=doc_type, feature=feature, date=date, graph=graph
            )
            replace_with_link()
            return docs

        monkeypatch.setattr(query, "list_documents", listing_then_replace)
    else:
        replace_with_link()

    async with Client(create_server()) as client:
        rows = data_of(
            await client.call_tool(
                "find", {"type": ["adr"], "text": "corpus-", "body": "full", "limit": 5}
            )
        )

    assert [row["name"] for row in rows] == [safe.stem]
    assert rows[0]["body"] == safe.read_bytes().decode("utf-8")
    assert rows[0]["blob_hash"] == git_blob_oid(safe.read_bytes())
    assert rows[0]["resource_uri"] == safe.as_uri()
