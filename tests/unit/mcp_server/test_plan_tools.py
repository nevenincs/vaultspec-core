"""Tests for the ``plan_progress`` and ``plan_edit`` MCP tools and the resolver.

Drives the real FastMCP server over the in-memory session transport against
a :class:`WorkspaceFactory`-installed vault on the real filesystem, with no
mocks, stubs, or skips.  Covers checked/unchecked batch marking with the
next-open-step readout, step add/insert/edit/remove with canonical-identifier
preservation and gap-no-reuse, and the ambiguous-feature resolution error
raised by the shared plan resolver.
"""

from __future__ import annotations

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from vaultspec_core.mcp_server.app import create_server
from vaultspec_core.mcp_server.plan_resolver import PlanResolutionError, resolve_plan
from vaultspec_core.plan.parser import parse_plan

from .conftest import data_of

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


async def _create_plan(client, feature: str, date: str | None = None) -> str:
    spec = {"feature": feature, "type": "plan", "tier": "L1"}
    if date is not None:
        spec["date"] = date
    result = await client.call_tool("create", {"documents": [spec]})
    payload = data_of(result)
    assert payload["status"] == "ok", payload
    return payload["items"][0]["path"]


async def _plan_edit(client, plan, operations):
    result = await client.call_tool(
        "plan_edit", {"plan": plan, "operations": operations}
    )
    return data_of(result)


async def _plan_progress(client, plan, steps):
    result = await client.call_tool("plan_progress", {"plan": plan, "steps": steps})
    return data_of(result)


def _plan_path(vault_root, feature: str):
    return next((vault_root / ".vault" / "plan").glob(f"*-{feature}-plan.md"))


# ---------------------------------------------------------------------------
# plan_edit
# ---------------------------------------------------------------------------


async def test_plan_edit_add_insert_edit_remove_preserves_ids(vault_root):
    """add/insert/edit/remove route through the core and never reuse an id."""
    mcp = create_server()
    async with create_connected_server_and_client_session(mcp) as client:
        await _create_plan(client, "editflow")
        added = await _plan_edit(
            client,
            "editflow",
            [
                {"operation": "add", "action": "First action", "scope": "src/a.py"},
                {"operation": "add", "action": "Second action", "scope": "src/b.py"},
            ],
        )
        assert added["status"] == "ok"
        assert [i["step_id"] for i in added["items"]] == ["S01", "S02"]

        # Insert before S01 allocates the next canonical id (S03), never S01.
        inserted = await _plan_edit(
            client,
            "editflow",
            [
                {
                    "operation": "insert",
                    "action": "Inserted at head",
                    "scope": "src/c.py",
                    "before": "S01",
                }
            ],
        )
        assert inserted["items"][0]["step_id"] == "S03"

        # Edit S02's action, then remove S01 (retires the id).
        edited = await _plan_edit(
            client,
            "editflow",
            [
                {"operation": "edit", "step_id": "S02", "action": "Second action v2"},
                {"operation": "remove", "step_id": "S01"},
            ],
        )
        assert edited["items"][0]["status"] == "updated"
        assert edited["items"][1]["status"] == "removed"
        assert edited["items"][1]["step_id"] == "S01"

        # Gap-no-reuse: the next add allocates S04, past the retired S01.
        after = await _plan_edit(
            client,
            "editflow",
            [{"operation": "add", "action": "Fourth", "scope": "src/d.py"}],
        )
        assert after["items"][0]["step_id"] == "S04"

        # The on-disk plan reflects the surviving canonical ids and the edit.
        text = _plan_path(vault_root, "editflow").read_text(encoding="utf-8")
        plan = parse_plan(text)
        ids = [s.canonical_id for s in plan.steps]
        assert "S01" not in ids
        assert {"S02", "S03", "S04"}.issubset(set(ids))
        s02 = next(s for s in plan.steps if s.canonical_id == "S02")
        assert s02.action == "Second action v2"


async def test_plan_edit_failed_op_does_not_abort_batch(vault_root):
    """A bad op fails per-item while a good op in the same batch still applies."""
    mcp = create_server()
    async with create_connected_server_and_client_session(mcp) as client:
        await _create_plan(client, "partialedit")
        result = await _plan_edit(
            client,
            "partialedit",
            [
                {"operation": "add", "action": "Good", "scope": "src/x.py"},
                {"operation": "edit", "step_id": "S99", "action": "nope"},
            ],
        )
        assert result["status"] == "mixed"
        assert result["items"][0]["status"] == "created"
        assert result["items"][1]["status"] == "failed"
        assert result["items"][1]["error"] is not None


async def test_plan_edit_empty_batch_is_protocol_error(vault_root):
    """An empty operation list is a whole-call protocol error."""
    mcp = create_server()
    async with create_connected_server_and_client_session(mcp) as client:
        await _create_plan(client, "emptyedit")
        result = await client.call_tool(
            "plan_edit", {"plan": "emptyedit", "operations": []}
        )
        assert result.isError


# ---------------------------------------------------------------------------
# plan_progress
# ---------------------------------------------------------------------------


async def test_plan_progress_check_uncheck_and_next_open_step(vault_root):
    """Marking a step advances completion and reports the next open step."""
    mcp = create_server()
    async with create_connected_server_and_client_session(mcp) as client:
        await _create_plan(client, "progressfeat")
        await _plan_edit(
            client,
            "progressfeat",
            [
                {"operation": "add", "action": "One", "scope": "src/a.py"},
                {"operation": "add", "action": "Two", "scope": "src/b.py"},
            ],
        )
        checked = await _plan_progress(
            client, "progressfeat", [{"step_id": "S01", "state": "checked"}]
        )
        assert checked["status"] == "ok"
        assert checked["items"][0]["status"] == "updated"
        assert checked["steps_completed"] == 1
        assert checked["total_steps"] == 2
        assert checked["next_open_step"].endswith("S02")

        # Re-checking the same step is an idempotent no-op.
        again = await _plan_progress(
            client, "progressfeat", [{"step_id": "S01", "state": "checked"}]
        )
        assert again["items"][0]["status"] == "unchanged"
        assert again["steps_completed"] == 1

        # Unchecking re-opens the step.
        reopened = await _plan_progress(
            client, "progressfeat", [{"step_id": "S01", "state": "unchecked"}]
        )
        assert reopened["items"][0]["status"] == "updated"
        assert reopened["steps_completed"] == 0


async def test_plan_progress_unknown_step_fails_item(vault_root):
    """An unknown step id is a per-item failure, not a whole-call error."""
    mcp = create_server()
    async with create_connected_server_and_client_session(mcp) as client:
        await _create_plan(client, "unknownstep")
        await _plan_edit(
            client,
            "unknownstep",
            [{"operation": "add", "action": "Only", "scope": "src/a.py"}],
        )
        result = await _plan_progress(
            client,
            "unknownstep",
            [
                {"step_id": "S01", "state": "checked"},
                {"step_id": "S99", "state": "checked"},
            ],
        )
        assert result["status"] == "mixed"
        assert result["items"][0]["status"] == "updated"
        assert result["items"][1]["status"] == "failed"


async def test_plan_progress_unresolvable_plan_is_protocol_error(vault_root):
    """An unresolvable plan address surfaces as a whole-call protocol error."""
    mcp = create_server()
    async with create_connected_server_and_client_session(mcp) as client:
        result = await client.call_tool(
            "plan_progress",
            {"plan": "no-such-plan", "steps": [{"step_id": "S01", "state": "checked"}]},
        )
        assert result.isError


# ---------------------------------------------------------------------------
# resolver
# ---------------------------------------------------------------------------


async def test_resolver_ambiguous_feature_raises(vault_root):
    """A feature owning two plans is a structured ambiguity error, not a guess."""
    mcp = create_server()
    async with create_connected_server_and_client_session(mcp) as client:
        await _create_plan(client, "twoplans", date="2026-07-09")
        await _create_plan(client, "twoplans", date="2026-07-10")

    # Two plans share the feature: addressing by feature is ambiguous, while
    # addressing by a unique stem still resolves.
    with pytest.raises(PlanResolutionError) as excinfo:
        resolve_plan(vault_root, "twoplans")
    assert len(excinfo.value.candidates) == 2

    stem = "2026-07-09-twoplans-plan"
    resolved = resolve_plan(vault_root, stem)
    assert resolved.stem == stem


async def test_resolver_unknown_target_raises(vault_root):
    """An address matching no plan raises with no candidates."""
    with pytest.raises(PlanResolutionError) as excinfo:
        resolve_plan(vault_root, "nothing-here")
    assert excinfo.value.candidates == []
