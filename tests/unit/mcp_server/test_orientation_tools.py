"""Tests for the find-extend and the ``status`` and ``check`` MCP tools.

Drives the real FastMCP server over the in-memory session transport against
a :class:`WorkspaceFactory`-installed vault on the real filesystem, with no
mocks, stubs, or skips.  Covers the find-extend contract (per-document
``blob_hash`` and ``resource_uri``, orientation-sourced lifecycle status),
the ``status`` rollup and targeted trace shapes, and the ``check`` suite
clean and with findings (with and without ``fix``).
"""

from __future__ import annotations

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from vaultspec_core.mcp_server.app import create_server
from vaultspec_core.vaultcore.blob_hash import git_blob_oid

from .conftest import data_of

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


async def _create(client, documents):
    result = await client.call_tool("create", {"documents": documents})
    return data_of(result)


# ---------------------------------------------------------------------------
# find extend
# ---------------------------------------------------------------------------


async def test_find_document_mode_returns_blob_hash_and_resource_uri(vault_root):
    """Document-search rows carry the current blob hash and a resource link."""
    mcp = create_server()
    async with create_connected_server_and_client_session(mcp) as client:
        await _create(client, [{"feature": "findext-feat", "type": "adr"}])
        result = await client.call_tool("find", {"feature": "findext-feat"})
        docs = data_of(result)
        assert len(docs) >= 1
        doc = docs[0]
        assert doc["type"] == "adr"
        assert doc["resource_uri"].startswith("file://")
        # The returned blob hash is the true git blob OID of the on-disk bytes.
        adr = next((vault_root / ".vault" / "adr").glob("*-findext-feat-adr.md"))
        assert doc["blob_hash"] == git_blob_oid(adr.read_bytes())


async def test_find_feature_status_sourced_from_orientation(vault_root):
    """A feature with an ADR and a plan reads back as ``Planned`` via orientation."""
    mcp = create_server()
    async with create_connected_server_and_client_session(mcp) as client:
        await _create(
            client,
            [
                {"feature": "statusfeat", "type": "adr"},
                {"feature": "statusfeat", "type": "plan"},
            ],
        )
        result = await client.call_tool("find", {"json": True})
        features = data_of(result)
        feat = next((f for f in features if f["name"] == "statusfeat"), None)
        assert feat is not None
        # Plan present, no closed steps -> Planned (orientation-derived).
        assert feat["status"] == "Planned"
        assert feat["has_plan"] is True


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


async def test_status_rollup_lists_features_and_version(vault_root):
    """The unparameterized status returns a rollup with the tool-schema version."""
    mcp = create_server()
    async with create_connected_server_and_client_session(mcp) as client:
        await _create(client, [{"feature": "rollupfeat", "type": "adr"}])
        result = await client.call_tool("status", {})
        payload = data_of(result)
        assert payload["kind"] == "rollup"
        assert payload["tool_schema_version"]
        names = {f["name"] for f in payload["features"]}
        assert "rollupfeat" in names
        # Orientation carries no blob hashes.
        assert "blob_hash" not in payload


async def test_status_trace_targets_a_feature(vault_root):
    """A feature target returns a grounding trace over its plan."""
    mcp = create_server()
    async with create_connected_server_and_client_session(mcp) as client:
        await _create(
            client,
            [
                {"feature": "tracefeat", "type": "adr"},
                {"feature": "tracefeat", "type": "plan"},
            ],
        )
        result = await client.call_tool("status", {"target": "tracefeat"})
        payload = data_of(result)
        assert payload["kind"] == "trace"
        assert payload["trace_kind"] == "feature"
        assert len(payload["plans"]) == 1
        assert "tracefeat" in payload["plans"][0]["stem"]


async def test_status_unresolvable_target_is_protocol_error(vault_root):
    """An unresolvable trace target surfaces as a whole-call protocol error."""
    mcp = create_server()
    async with create_connected_server_and_client_session(mcp) as client:
        result = await client.call_tool("status", {"target": "no-such-feature-or-plan"})
        assert result.isError


# ---------------------------------------------------------------------------
# check
# ---------------------------------------------------------------------------


async def test_check_clean_vault_reports_ok(vault_root):
    """A freshly-installed vault checks clean."""
    mcp = create_server()
    async with create_connected_server_and_client_session(mcp) as client:
        result = await client.call_tool("check", {})
        payload = data_of(result)
        assert payload["status"] == "ok"
        assert payload["total_errors"] == 0
        assert payload["fixed"] is False


async def test_check_reports_findings_for_broken_document(vault_root):
    """A dangling wiki-link raises error-severity findings in the suite."""
    adr = vault_root / ".vault" / "adr" / "2026-07-09-brokenfeat-adr.md"
    adr.write_text(
        "---\n"
        "tags:\n  - '#adr'\n  - '#brokenfeat'\n"
        "date: '2026-07-09'\n"
        "modified: '2026-07-09'\n"
        "related:\n  - '[[does-not-exist]]'\n"
        "---\n\n# brokenfeat adr\n\nBody with a [[does-not-exist]] link.\n",
        encoding="utf-8",
    )
    mcp = create_server()
    async with create_connected_server_and_client_session(mcp) as client:
        result = await client.call_tool("check", {})
        payload = data_of(result)
        assert payload["status"] == "failed"
        assert payload["total_errors"] >= 1
        checks_with_errors = {
            f["check"] for f in payload["findings"] if f["severity"] == "error"
        }
        assert "dangling" in checks_with_errors


async def test_check_fix_flag_is_reported(vault_root):
    """The ``fix`` flag runs the repairing pass and is echoed in the result."""
    mcp = create_server()
    async with create_connected_server_and_client_session(mcp) as client:
        result = await client.call_tool("check", {"fix": True})
        payload = data_of(result)
        assert payload["fixed"] is True
        assert payload["status"] == "ok"
