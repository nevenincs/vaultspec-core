"""Tests for the batch-native MCP ``create`` tool.

Drives the real FastMCP server over the in-memory session transport against
a :class:`WorkspaceFactory`-installed vault on the real filesystem.  Covers
the intra-batch lifecycle dependency (an item validated against the vault
state including earlier same-batch items), the partial-failure envelope (a
good and a bad item aggregate to ``mixed`` while later items still apply),
and the automatic feature-index regeneration side effect.
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


async def test_create_batch_intra_batch_lifecycle_dependency(vault_root):
    """A single batch scaffolds research -> ADR -> plan -> exec coherently.

    ``exec`` hard-requires a plan and an ADR; because items apply
    sequentially and validation runs against the on-disk vault, the earlier
    same-batch items satisfy the later exec item without a second call.
    """
    mcp = create_server()
    async with create_connected_server_and_client_session(mcp) as client:
        payload = await _create(
            client,
            [
                {"feature": "lifecycle-feat", "type": "research"},
                {"feature": "lifecycle-feat", "type": "adr"},
                {"feature": "lifecycle-feat", "type": "plan"},
                {"feature": "lifecycle-feat", "type": "exec"},
            ],
        )
        assert payload["status"] == "ok"
        statuses = [item["status"] for item in payload["items"]]
        assert statuses == ["created", "created", "created", "created"]
        assert (
            vault_root / ".vault" / "adr" / "2026-07-09-lifecycle-feat-adr.md"
        ).exists() or any(
            (vault_root / ".vault" / "adr").glob("*-lifecycle-feat-adr.md")
        )
        assert any((vault_root / ".vault" / "plan").glob("*-lifecycle-feat-plan.md"))
        # Every created item returns a post-write blob hash for chaining.
        assert all(item["blob_hash"] for item in payload["items"])


async def test_create_exec_before_plan_fails_but_later_item_applies(vault_root):
    """A bad item fails per-item while good items on both sides still apply.

    An ``exec`` created before any plan exists is a hard dependency error;
    the batch aggregates to ``mixed``, the failure is reported in place, and
    the item after it is still scaffolded.
    """
    mcp = create_server()
    async with create_connected_server_and_client_session(mcp) as client:
        payload = await _create(
            client,
            [
                {"feature": "partial-feat", "type": "adr"},
                {"feature": "partial-feat", "type": "exec"},  # no plan yet -> ERROR
                {"feature": "other-feat", "type": "research"},
            ],
        )
        assert payload["status"] == "mixed"
        items = payload["items"]
        assert items[0]["status"] == "created"
        assert items[1]["status"] == "failed"
        assert items[1]["error"] is not None
        assert "plan" in items[1]["error"]["message"].lower()
        # The item after the failure is still applied.
        assert items[2]["status"] == "created"
        research_dir = vault_root / ".vault" / "research"
        assert any(research_dir.glob("*-other-feat-research.md"))


async def test_create_regenerates_feature_index(vault_root):
    """Creating documents regenerates the affected feature's index as a side effect."""
    mcp = create_server()
    async with create_connected_server_and_client_session(mcp) as client:
        payload = await _create(
            client,
            [
                {"feature": "index-feat", "type": "adr"},
                {"feature": "index-feat", "type": "plan"},
            ],
        )
        assert payload["status"] == "ok"
        index_path = vault_root / ".vault" / "index" / "index-feat.index.md"
        assert index_path.exists()
        index_text = index_path.read_text(encoding="utf-8")
        assert "#index-feat" in index_text


async def test_create_rejects_index_type_per_item(vault_root):
    """An ``index`` spec is a per-item failure, not a whole-call error."""
    mcp = create_server()
    async with create_connected_server_and_client_session(mcp) as client:
        payload = await _create(
            client,
            [{"feature": "idx-reject", "type": "index"}],
        )
        assert payload["status"] == "failed"
        assert payload["items"][0]["status"] == "failed"
        assert "auto-generated" in payload["items"][0]["error"]["message"]


async def test_create_empty_batch_raises_protocol_error(vault_root):
    """An empty batch is a malformed whole-call input surfaced as ``isError``."""
    mcp = create_server()
    async with create_connected_server_and_client_session(mcp) as client:
        result = await client.call_tool("create", {"documents": []})
        assert result.isError


async def test_create_seed_content_appended(vault_root):
    """Seed content is appended through the shared edit engine as a section."""
    mcp = create_server()
    async with create_connected_server_and_client_session(mcp) as client:
        payload = await _create(
            client,
            [
                {
                    "feature": "seed-feat",
                    "type": "adr",
                    "content": "A distinctive seeded paragraph.",
                }
            ],
        )
        assert payload["status"] == "ok"
        adr = next((vault_root / ".vault" / "adr").glob("*-seed-feat-adr.md"))
        text = adr.read_text(encoding="utf-8")
        assert "A distinctive seeded paragraph." in text


async def test_create_topic_infix_scaffolds_second_reference(vault_root):
    """A topic-infixed spec scaffolds a second same-day reference document."""
    mcp = create_server()
    async with create_connected_server_and_client_session(mcp) as client:
        payload = await _create(
            client,
            [
                {"feature": "infix-feat", "type": "reference"},
                {
                    "feature": "infix-feat",
                    "type": "reference",
                    "topic": "engine-wire",
                },
            ],
        )
        assert payload["status"] == "ok"
        ref_dir = vault_root / ".vault" / "reference"
        assert any(ref_dir.glob("*-infix-feat-reference.md"))
        assert any(ref_dir.glob("*-infix-feat-engine-wire-reference.md"))


async def test_create_topic_rejected_for_non_admitting_type(vault_root):
    """A topic on an adr spec is a per-item failure."""
    mcp = create_server()
    async with create_connected_server_and_client_session(mcp) as client:
        payload = await _create(
            client,
            [{"feature": "infix-feat", "type": "adr", "topic": "second"}],
        )
        assert payload["status"] == "failed"
        assert "topic is only valid" in payload["items"][0]["error"]["message"]


async def test_create_mixed_batch_topic_failure_beside_success(vault_root):
    """A topic-rejected item fails per-item while its batch siblings apply."""
    mcp = create_server()
    async with create_connected_server_and_client_session(mcp) as client:
        payload = await _create(
            client,
            [
                {"feature": "mixed-feat", "type": "reference", "topic": "wire"},
                {"feature": "mixed-feat", "type": "adr", "topic": "second"},
                {"feature": "mixed-feat", "type": "research"},
            ],
        )
        assert payload["status"] == "mixed"
        items = payload["items"]
        assert items[0]["status"] == "created"
        assert items[1]["status"] == "failed"
        assert "topic is only valid" in items[1]["error"]["message"]
        assert items[2]["status"] == "created"
