"""Tests for the ``plan_progress`` and ``plan_edit`` MCP tools and the resolver.

Drives the real MCPServer over the in-memory client transport against
a :class:`WorkspaceFactory`-installed vault on the real filesystem, with no
mocks, stubs, or skips.  Covers checked/unchecked batch marking with the
next-open-step readout, step add/insert/edit/remove with canonical-identifier
preservation and gap-no-reuse, and the ambiguous-feature resolution error
raised by the shared plan resolver.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from mcp import Client

from vaultspec_core.mcp_server.app import create_server
from vaultspec_core.mcp_server.plan_resolver import PlanResolutionError, resolve_plan
from vaultspec_core.plan.parser import parse_plan

from .conftest import data_of

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


async def _create_plan(client: Client, feature: str, date: str | None = None) -> str:
    spec: dict[str, Any] = {"feature": feature, "type": "plan", "tier": "L1"}
    if date is not None:
        spec["date"] = date
    result = await client.call_tool("create", {"documents": [spec]})
    payload = data_of(result)
    assert payload["status"] == "ok", payload
    return payload["items"][0]["path"]


async def _plan_edit(
    client: Client, plan: str, operations: list[dict[str, Any]]
) -> Any:
    result = await client.call_tool(
        "plan_edit", {"plan": plan, "operations": operations}
    )
    return data_of(result)


async def _plan_progress(client: Client, plan: str, steps: list[dict[str, Any]]) -> Any:
    result = await client.call_tool("plan_progress", {"plan": plan, "steps": steps})
    return data_of(result)


def _plan_path(vault_root: Path, feature: str) -> Path:
    return next((vault_root / ".vault" / "plan").glob(f"*-{feature}-plan.md"))


# ---------------------------------------------------------------------------
# plan_edit
# ---------------------------------------------------------------------------


async def test_plan_edit_add_insert_edit_remove_preserves_ids(vault_root: Path) -> None:
    """add/insert/edit/remove route through the core and never reuse an id."""
    mcp = create_server()
    async with Client(mcp) as client:
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


async def test_plan_edit_preserves_future_frontmatter_and_reattests_body(
    vault_root: Path,
) -> None:
    """The MCP write path carries future YAML through a truthful re-attestation."""
    from vaultspec_core.vaultcore import parse_frontmatter
    from vaultspec_core.vaultcore.body_hash import document_body_digest

    mcp = create_server()
    async with Client(mcp) as client:
        await _create_plan(client, "futuremcp")
        path = _plan_path(vault_root, "futuremcp")
        source = path.read_text(encoding="utf-8").replace(
            "tier: L1\n",
            "tier: L1\n"
            "future_null: null\n"
            "future_values: [one, 2, true]\n"
            "future_map: {mode: strict, retries: 3}\n",
        )
        path.write_text(source, encoding="utf-8")

        result = await _plan_edit(
            client,
            "futuremcp",
            [{"operation": "add", "action": "Future safe", "scope": "src/f.py"}],
        )

        assert result["status"] == "ok"
        persisted = path.read_text(encoding="utf-8")
        metadata, _ = parse_frontmatter(persisted)
        assert metadata["future_null"] is None
        assert metadata["future_values"] == ["one", 2, True]
        assert metadata["future_map"] == {"mode": "strict", "retries": 3}
        assert persisted.count("body_hash:") == 1
        assert metadata["body_hash"] == document_body_digest(persisted)


async def test_plan_edit_failed_op_does_not_abort_batch(vault_root: Path) -> None:
    """A bad op fails per-item while a good op in the same batch still applies."""
    mcp = create_server()
    async with Client(mcp) as client:
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


async def test_plan_edit_unknown_operation_fails_the_item(vault_root: Path) -> None:
    """An unrecognised verb fails its item and echoes the verb it was given."""
    mcp = create_server()
    async with Client(mcp) as client:
        await _create_plan(client, "unknownverb")
        result = await _plan_edit(
            client,
            "unknownverb",
            [{"operation": "retire", "step_id": "S01"}],
        )
        assert result["status"] == "failed"
        item = result["items"][0]
        assert item["operation"] == "retire"
        assert item["error"]["message"] == "Unknown plan_edit operation: 'retire'"
        assert result["total_steps"] == 0


async def test_plan_edit_missing_required_fields_fail_per_operation(
    vault_root: Path,
) -> None:
    """Each verb reports its own missing-precondition message."""
    mcp = create_server()
    async with Client(mcp) as client:
        await _create_plan(client, "preconditions")
        result = await _plan_edit(
            client,
            "preconditions",
            [
                {"operation": "add", "action": "No scope"},
                {"operation": "insert", "scope": "src/x.py"},
                {"operation": "edit", "action": "No step id"},
                {"operation": "remove"},
            ],
        )
        assert result["status"] == "failed"
        messages = [item["error"]["message"] for item in result["items"]]
        assert messages == [
            "'add' requires 'action' and 'scope'",
            "'insert' requires 'action' and 'scope'",
            "'edit' requires 'step_id'",
            "'remove' requires 'step_id'",
        ]
        assert [item["operation"] for item in result["items"]] == [
            "add",
            "insert",
            "edit",
            "remove",
        ]
        plan = parse_plan(_plan_path(vault_root, "preconditions").read_text("utf-8"))
        assert plan.steps == []


async def test_plan_edit_empty_batch_is_protocol_error(vault_root: Path) -> None:
    """An empty operation list is a whole-call protocol error."""
    mcp = create_server()
    async with Client(mcp) as client:
        await _create_plan(client, "emptyedit")
        result = await client.call_tool(
            "plan_edit", {"plan": "emptyedit", "operations": []}
        )
        assert result.is_error


async def test_plan_edit_refuses_a_scope_the_row_cannot_carry(
    vault_root: Path,
) -> None:
    """A step the document cannot carry fails its item instead of succeeding.

    A scope carrying the row grammar's own ``;`` delimiter cannot be expressed
    in the scope span. The refusal happens at the command boundary, before any
    serialisation, so the operator is told what to change and the plan is left
    byte-identical rather than handed a ``created`` result the document does
    not back (issues #296 and #313).
    """
    mcp = create_server()
    async with Client(mcp) as client:
        await _create_plan(client, "roundtrip")
        path = _plan_path(vault_root, "roundtrip")
        before = path.read_bytes()

        result = await _plan_edit(
            client,
            "roundtrip",
            [
                {
                    "operation": "add",
                    "action": "reconcile the ledger",
                    "scope": "src/a.py; src/b.py",
                }
            ],
        )

        assert result["status"] == "failed"
        assert "may not contain" in result["items"][0]["error"]["message"]
        assert path.read_bytes() == before


async def test_plan_edit_restores_the_plan_when_the_write_does_not_verify(
    vault_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A post-write verification failure leaves the document byte-identical.

    The divergence is forced by a concurrent writer clobbering the file between
    the write and the re-read - the race the post-write guard exists to catch
    (issue #296). The guard must fail the call *and* restore the pre-mutation
    bytes (issue #313).
    """
    from vaultspec_core.plan import write_guard

    mcp = create_server()
    async with Client(mcp) as client:
        await _create_plan(client, "clobbered")
        path = _plan_path(vault_root, "clobbered")
        before = path.read_bytes()

        real_verify = write_guard.verify_plan_write

        def clobber_then_verify(target: Path, expected_text: str, expected_plan: Any):
            target.write_text("clobbered by another writer\n", encoding="utf-8")
            return real_verify(target, expected_text, expected_plan)

        monkeypatch.setattr(write_guard, "verify_plan_write", clobber_then_verify)

        result = await client.call_tool(
            "plan_edit",
            {
                "plan": "clobbered",
                "operations": [
                    {"operation": "add", "action": "Any action", "scope": "src/a.py"}
                ],
            },
        )

        assert result.is_error
        texts = [getattr(block, "text", "") for block in result.content]
        assert any("write verification failed" in text for text in texts), texts
        assert path.read_bytes() == before


async def test_plan_edit_accepts_a_semicolon_in_the_action(
    vault_root: Path,
) -> None:
    """An action may carry its own semicolons on the MCP surface too.

    The delimiter reproduction from issue #313: the row used to be written and
    then failed by post-write verification, leaving the malformed Step
    persisted after the call reported an error.
    """
    mcp = create_server()
    async with Client(mcp) as client:
        await _create_plan(client, "semicolonfeat")
        await _plan_edit(
            client,
            "semicolonfeat",
            [
                {
                    "operation": "add",
                    "action": "Ground the contract; implement the reader",
                    "scope": "src/cadrumo/core/_credentials.py",
                }
            ],
        )


# ---------------------------------------------------------------------------
# plan_progress
# ---------------------------------------------------------------------------


async def test_plan_progress_check_uncheck_and_next_open_step(vault_root: Path) -> None:
    """Marking a step advances completion and reports the next open step."""
    mcp = create_server()
    async with Client(mcp) as client:
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


async def test_plan_progress_unknown_step_fails_item(vault_root: Path) -> None:
    """An unknown step id is a per-item failure, not a whole-call error."""
    mcp = create_server()
    async with Client(mcp) as client:
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


async def test_plan_progress_unresolvable_plan_is_protocol_error(
    vault_root: Path,
) -> None:
    """An unresolvable plan address surfaces as a whole-call protocol error."""
    mcp = create_server()
    async with Client(mcp) as client:
        result = await client.call_tool(
            "plan_progress",
            {"plan": "no-such-plan", "steps": [{"step_id": "S01", "state": "checked"}]},
        )
        assert result.is_error


# ---------------------------------------------------------------------------
# resolver
# ---------------------------------------------------------------------------


async def test_resolver_ambiguous_feature_raises(vault_root: Path) -> None:
    """A feature owning two plans is a structured ambiguity error, not a guess."""
    mcp = create_server()
    async with Client(mcp) as client:
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


async def test_resolver_unknown_target_raises(vault_root: Path) -> None:
    """An address matching no plan raises with no candidates."""
    with pytest.raises(PlanResolutionError) as excinfo:
        resolve_plan(vault_root, "nothing-here")
    assert excinfo.value.candidates == []
