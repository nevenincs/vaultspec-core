"""Tests for the batch-native MCP ``edit`` tool.

Drives the real FastMCP server over the in-memory session transport against
a :class:`WorkspaceFactory`-installed vault on the real filesystem.  Covers
the blob-hash conflict path (a stale hash fails the item as ``conflict``
without writing), ``section_not_found`` for a missing heading, intra-batch
same-document sequencing with the hash set on the first op only, and the
post-write hash chaining from one op into the next.
"""

from __future__ import annotations

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from vaultspec_core.mcp_server.app import create_server
from vaultspec_core.vaultcore.blob_hash import git_blob_oid

from .conftest import data_of

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


async def _create_adr(client, feature: str) -> str:
    """Scaffold one ADR and return its stem."""
    result = await client.call_tool(
        "create", {"documents": [{"feature": feature, "type": "adr"}]}
    )
    payload = data_of(result)
    assert payload["status"] == "ok", payload
    return payload["items"][0]["path"]


async def _edit(client, operations):
    result = await client.call_tool("edit", {"operations": operations})
    return data_of(result)


async def test_edit_set_body_returns_post_write_hash(vault_root):
    """A ``set_body`` edit updates the file and returns the post-write blob hash."""
    mcp = create_server()
    async with create_connected_server_and_client_session(mcp) as client:
        await _create_adr(client, "sb-feat")
        adr = next((vault_root / ".vault" / "adr").glob("*-sb-feat-adr.md"))
        payload = await _edit(
            client,
            [
                {
                    "target": adr.stem,
                    "operation": "set_body",
                    "content": "# Replaced\n\nWholly new body prose.",
                }
            ],
        )
        assert payload["status"] == "ok"
        item = payload["items"][0]
        assert item["status"] == "updated"
        assert "Wholly new body prose." in adr.read_text(encoding="utf-8")
        assert item["blob_hash"] == git_blob_oid(adr.read_bytes())


async def test_edit_blob_hash_conflict(vault_root):
    """A stale ``expected_blob_hash`` fails the item as a conflict without writing."""
    mcp = create_server()
    async with create_connected_server_and_client_session(mcp) as client:
        await _create_adr(client, "conflict-feat")
        adr = next((vault_root / ".vault" / "adr").glob("*-conflict-feat-adr.md"))
        original = adr.read_bytes()
        stale_hash = git_blob_oid(b"stale bytes that never matched")
        payload = await _edit(
            client,
            [
                {
                    "target": adr.stem,
                    "operation": "set_body",
                    "content": "# Nope\n\nShould not be written.",
                    "expected_blob_hash": stale_hash,
                }
            ],
        )
        assert payload["status"] == "failed"
        item = payload["items"][0]
        assert item["status"] == "failed"
        assert item["error"]["conflict"] is True
        # The file is untouched.
        assert adr.read_bytes() == original


async def test_edit_section_not_found(vault_root):
    """Addressing a heading that does not exist fails the item, not the call."""
    mcp = create_server()
    async with create_connected_server_and_client_session(mcp) as client:
        await _create_adr(client, "miss-feat")
        adr = next((vault_root / ".vault" / "adr").glob("*-miss-feat-adr.md"))
        payload = await _edit(
            client,
            [
                {
                    "target": adr.stem,
                    "operation": "replace_section",
                    "section": "## No Such Heading Anywhere",
                    "content": "irrelevant",
                }
            ],
        )
        assert payload["status"] == "failed"
        item = payload["items"][0]
        assert item["status"] == "failed"
        assert item["error"]["section_not_found"] is True


async def test_edit_intra_batch_same_document_hash_on_first_op_only(vault_root):
    """Two ops on one document sequence correctly with the hash on the first only.

    The first op carries the current blob hash; the second omits it and is
    validated against the on-disk bytes the first op produced.  Both apply,
    and the second item's post-write hash reflects the accumulated edits.
    """
    mcp = create_server()
    async with create_connected_server_and_client_session(mcp) as client:
        await _create_adr(client, "seq-feat")
        adr = next((vault_root / ".vault" / "adr").glob("*-seq-feat-adr.md"))
        current_hash = git_blob_oid(adr.read_bytes())
        payload = await _edit(
            client,
            [
                {
                    "target": adr.stem,
                    "operation": "set_body",
                    "content": "# Seq\n\n## Alpha\n\nFirst.",
                    "expected_blob_hash": current_hash,
                },
                {
                    "target": adr.stem,
                    "operation": "append_section",
                    "section": "## Alpha",
                    "content": "Appended second.",
                },
            ],
        )
        assert payload["status"] == "ok"
        first, second = payload["items"]
        assert first["status"] == "updated"
        assert second["status"] == "updated"
        text = adr.read_text(encoding="utf-8")
        assert "First." in text
        assert "Appended second." in text
        # The second op's returned hash matches the final on-disk bytes.
        assert second["blob_hash"] == git_blob_oid(adr.read_bytes())


async def test_edit_post_write_hash_chains_across_documents(vault_root):
    """The returned hash of one op is a valid guard for a later op on that doc."""
    mcp = create_server()
    async with create_connected_server_and_client_session(mcp) as client:
        await _create_adr(client, "chain-feat")
        adr = next((vault_root / ".vault" / "adr").glob("*-chain-feat-adr.md"))
        first = await _edit(
            client,
            [
                {
                    "target": adr.stem,
                    "operation": "set_body",
                    "content": "# Chain\n\n## Body\n\nOne.",
                }
            ],
        )
        chained_hash = first["items"][0]["blob_hash"]
        # Re-using the returned hash as the guard for the next edit succeeds,
        # proving it is the true post-write on-disk hash.
        second = await _edit(
            client,
            [
                {
                    "target": adr.stem,
                    "operation": "replace_section",
                    "section": "## Body",
                    "content": "Two.",
                    "expected_blob_hash": chained_hash,
                }
            ],
        )
        assert second["status"] == "ok"
        assert second["items"][0]["status"] == "updated"
        assert "Two." in adr.read_text(encoding="utf-8")


async def test_edit_empty_batch_raises_protocol_error(vault_root):
    """An empty operation list is a malformed whole-call input surfaced as isError."""
    mcp = create_server()
    async with create_connected_server_and_client_session(mcp) as client:
        result = await client.call_tool("edit", {"operations": []})
        assert result.isError


async def test_edit_unresolvable_target_fails_item(vault_root):
    """An unresolvable target is a per-item failure, not a whole-call error."""
    mcp = create_server()
    async with create_connected_server_and_client_session(mcp) as client:
        payload = await _edit(
            client,
            [
                {
                    "target": "no-such-document-anywhere",
                    "operation": "set_body",
                    "content": "x",
                }
            ],
        )
        assert payload["status"] == "failed"
        assert payload["items"][0]["status"] == "failed"
        assert "resolve" in payload["items"][0]["error"]["message"].lower()
