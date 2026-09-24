"""Tests for the find-extend and the ``status`` and ``check`` MCP tools.

Drives the real MCPServer over the in-memory client transport against
a :class:`WorkspaceFactory`-installed vault on the real filesystem, with no
mocks, stubs, or skips.  Covers the find-extend contract (per-document
``blob_hash`` and ``resource_uri``, orientation-sourced lifecycle status),
the ``status`` rollup and targeted trace shapes, and the ``check`` suite
clean and with findings (with and without ``fix``).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest
from mcp import Client

from vaultspec_core.config import HostedSearchConfig
from vaultspec_core.core.diagnosis.collectors_companion import RAG_DISTRIBUTION_NAME
from vaultspec_core.mcp_server.app import create_server
from vaultspec_core.search import (
    DiscoveryCapability,
    discovery_capability,
    discovery_fields,
)
from vaultspec_core.vaultcore.blob_hash import git_blob_oid

from .conftest import data_of

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]


async def _create(client: Client, documents: list[dict[str, Any]]) -> Any:
    result = await client.call_tool("create", {"documents": documents})
    return data_of(result)


# ---------------------------------------------------------------------------
# find extend
# ---------------------------------------------------------------------------


async def test_find_document_mode_returns_blob_hash_and_resource_uri(
    vault_root: Path,
) -> None:
    """Document-search rows carry the current blob hash and a resource link."""
    mcp = create_server()
    async with Client(mcp) as client:
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


async def test_find_feature_status_sourced_from_orientation(vault_root: Path) -> None:
    """A feature with an ADR and a plan reads back as ``Planned`` via orientation."""
    mcp = create_server()
    async with Client(mcp) as client:
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


async def test_status_rollup_lists_features_and_version(vault_root: Path) -> None:
    """The unparameterized status returns a rollup with the tool-schema version."""
    mcp = create_server()
    async with Client(mcp) as client:
        await _create(client, [{"feature": "rollupfeat", "type": "adr"}])
        result = await client.call_tool("status", {})
        payload = data_of(result)
        assert payload["kind"] == "rollup"
        assert payload["tool_schema_version"]
        names = {f["name"] for f in payload["features"]}
        assert "rollupfeat" in names
        # Orientation carries no blob hashes.
        assert "blob_hash" not in payload


async def test_status_rollup_carries_the_backend_discovery_record(
    vault_root: Path,
) -> None:
    """The rollup's discovery keys are the search package's one projection."""
    mcp = create_server()
    async with Client(mcp) as client:
        payload = data_of(await client.call_tool("status", {}))

    expected = discovery_fields(discovery_capability(vault_root))
    # Key presence, not ``get``: an omitted key and a null one must not match.
    names = {"hosted_search", "companion"}
    discovery = {key: payload[key] for key in names & payload.keys()}
    assert discovery == json.loads(json.dumps(expected))
    assert payload["companion"]["package"] == RAG_DISTRIBUTION_NAME


def test_a_failed_companion_probe_omits_the_key_on_both_surfaces() -> None:
    """Both surfaces spread one projection, and it drops the key, never nulls it."""
    failed = DiscoveryCapability(
        hosted_search=HostedSearchConfig(configured=False, source=None),
        companion=None,
    )

    fields = discovery_fields(failed)

    assert "companion" not in fields
    assert fields["hosted_search"] == {"configured": False, "source": None}


async def test_status_schema_omits_null_only_where_the_wire_does(
    vault_root: Path,
) -> None:
    """An omitted key publishes no null branch; a key sent as null keeps one."""
    _ = vault_root
    tools = {tool.name: tool for tool in await create_server().list_tools()}
    schema = tools["status"].output_schema
    assert schema is not None

    properties = schema["properties"]
    # Absent outside rollup mode, never null.
    companion = properties["companion"]
    assert "anyOf" not in companion
    assert companion["type"] == "object"
    assert "null" not in json.dumps(properties["target"])
    # Always present, null when the plan has no open step.
    line = properties["plans_in_flight"]["items"]
    assert "next_open_step" in line["required"]
    assert line["properties"]["next_open_step"] == {"type": ["string", "null"]}
    # A dataclass field that may be null keeps null among its values.
    mode = companion["properties"]["mode"]
    assert None in mode["enum"]


async def test_status_trace_targets_a_feature(vault_root: Path) -> None:
    """A feature target returns a grounding trace over its plan."""
    mcp = create_server()
    async with Client(mcp) as client:
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


async def test_status_unresolvable_target_is_protocol_error(vault_root: Path) -> None:
    """An unresolvable trace target surfaces as a whole-call protocol error."""
    mcp = create_server()
    async with Client(mcp) as client:
        result = await client.call_tool("status", {"target": "no-such-feature-or-plan"})
        assert result.is_error


# ---------------------------------------------------------------------------
# check
# ---------------------------------------------------------------------------


async def test_check_clean_vault_reports_ok(vault_root: Path) -> None:
    """A freshly-installed vault checks clean."""
    mcp = create_server()
    async with Client(mcp) as client:
        result = await client.call_tool("check", {})
        payload = data_of(result)
        assert payload["status"] == "ok"
        assert payload["total_errors"] == 0
        assert payload["fixed"] is False


async def test_check_reports_findings_for_broken_document(vault_root: Path) -> None:
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
    async with Client(mcp) as client:
        result = await client.call_tool("check", {})
        payload = data_of(result)
        assert payload["status"] == "failed"
        assert payload["total_errors"] >= 1
        checks_with_errors = {
            f["check"] for f in payload["findings"] if f["severity"] == "error"
        }
        assert "dangling" in checks_with_errors


async def test_check_fix_flag_is_reported(vault_root: Path) -> None:
    """The ``fix`` flag runs the repairing pass and is echoed in the result."""
    mcp = create_server()
    async with Client(mcp) as client:
        result = await client.call_tool("check", {"fix": True})
        payload = data_of(result)
        assert payload["fixed"] is True
        assert payload["status"] == "ok"
