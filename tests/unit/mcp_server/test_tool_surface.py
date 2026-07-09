"""Full nine-tool surface integration test over the real ``create_server``.

Builds the production server through ``create_server`` on a
:class:`WorkspaceFactory`-installed vault and drives it over the in-memory
FastMCP session - no mocks, stubs, or skips. Asserts that exactly the nine
expected tools are registered with the ADR Q6 annotation matrix and an
``outputSchema`` each, exercises a representative call on every tool end-to-end
(including a gateway ``invoke`` of the real ``vault list`` verb), confirms a
whole-call failure surfaces as protocol ``isError``, and checks the shipped MCP
registry entry still launches this same server module unchanged.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from vaultspec_core import __version__
from vaultspec_core.mcp_server.app import create_server

from .conftest import data_of, vault_root  # noqa: F401 - re-exported fixture

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]

#: The nine tools the redesigned surface must advertise, and nothing else.
_EXPECTED_TOOLS = frozenset(
    {
        "status",
        "find",
        "create",
        "edit",
        "plan_progress",
        "plan_edit",
        "check",
        "discover",
        "invoke",
    }
)

#: The ADR Q6 annotation matrix: each tool mapped to the hints it must declare.
#: Read-only tools (status/find/discover) leave ``destructiveHint`` unset
#: (``None``), matching how their :class:`ToolAnnotations` are constructed.
_ANNOTATIONS = {
    "status": {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    "find": {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    "discover": {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    "create": {
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
    "edit": {
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False,
    },
    "plan_progress": {
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
    "plan_edit": {
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False,
    },
    "check": {
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
    "invoke": {
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False,
    },
}


async def test_surface_registers_exactly_nine_tools_with_schemas(vault_root):  # noqa: F811
    """``create_server`` advertises exactly the nine tools, schema'd and annotated."""
    mcp = create_server()
    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    assert names == _EXPECTED_TOOLS, names

    by_name = {t.name: t for t in tools}
    for name, expected in _ANNOTATIONS.items():
        tool = by_name[name]
        assert tool.outputSchema is not None, f"{name} declares no outputSchema"
        annotations = tool.annotations
        assert annotations is not None, f"{name} declares no annotations"
        for hint, value in expected.items():
            actual = getattr(annotations, hint)
            assert actual == value, f"{name}.{hint} == {actual!r}, expected {value!r}"


async def test_surface_instructions_name_the_tools_and_version(vault_root):  # noqa: F811
    """The server instructions string names the surface and carries the version."""
    mcp = create_server()
    instructions = mcp.instructions or ""
    assert __version__ in instructions
    for name in _EXPECTED_TOOLS:
        assert name in instructions, f"{name} missing from instructions"


async def test_surface_representative_call_per_tool(vault_root):  # noqa: F811
    """Every tool answers a representative call end-to-end on the real server."""
    mcp = create_server()
    async with create_connected_server_and_client_session(mcp) as client:
        # create: scaffold a full research/adr/plan lifecycle in one batch so
        # intra-batch dependency validation is exercised for real.
        created = data_of(
            await client.call_tool(
                "create",
                {
                    "documents": [
                        {"feature": "surface-probe", "type": "research"},
                        {"feature": "surface-probe", "type": "adr"},
                        {"feature": "surface-probe", "type": "plan", "tier": "L1"},
                    ]
                },
            )
        )
        assert created["status"] == "ok"
        assert [item["status"] for item in created["items"]] == [
            "created",
            "created",
            "created",
        ]
        research_stem = Path(created["items"][0]["path"]).stem

        # plan_edit: author a step onto the freshly-created plan.
        edited_plan = data_of(
            await client.call_tool(
                "plan_edit",
                {
                    "plan": "surface-probe",
                    "operations": [
                        {
                            "operation": "add",
                            "action": "Probe the surface",
                            "scope": "`src/x.py`",
                        }
                    ],
                },
            )
        )
        assert edited_plan["status"] == "ok"
        step_id = edited_plan["items"][0]["step_id"]
        assert step_id is not None

        # plan_progress: close the step just authored.
        progressed = data_of(
            await client.call_tool(
                "plan_progress",
                {
                    "plan": "surface-probe",
                    "steps": [{"step_id": step_id, "state": "checked"}],
                },
            )
        )
        assert progressed["status"] == "ok"
        assert progressed["steps_completed"] == 1

        # edit: replace the research document body through the shared engine.
        body_edited = data_of(
            await client.call_tool(
                "edit",
                {
                    "operations": [
                        {
                            "target": research_stem,
                            "operation": "set_body",
                            "content": "## Notes\n\nSurface probe edit.\n",
                        }
                    ]
                },
            )
        )
        assert body_edited["status"] == "ok"
        assert body_edited["items"][0]["status"] == "updated"
        assert body_edited["items"][0]["blob_hash"]

        # find: feature listing and document search both answer.
        listed = data_of(await client.call_tool("find", {}))
        assert any(row["name"] == "surface-probe" for row in listed)
        searched = data_of(
            await client.call_tool("find", {"feature": "surface-probe"})
        )
        assert searched and all(
            row.get("blob_hash") for row in searched
        ), searched

        # status: project rollup and a targeted trace.
        rollup = data_of(await client.call_tool("status", {}))
        assert rollup["kind"] == "rollup"
        assert rollup["tool_schema_version"] == __version__
        trace = data_of(
            await client.call_tool("status", {"target": "surface-probe"})
        )
        assert trace["kind"] == "trace"

        # check: run the health suite over the vault.
        checked = data_of(await client.call_tool("check", {}))
        assert checked["status"] in {"ok", "failed"}
        assert "checks" in checked

        # discover: rank the long-tail catalog for a known verb.
        discovered = data_of(
            await client.call_tool("discover", {"query": "list vault documents"})
        )
        assert "vault list" in {v["verb"] for v in discovered["verbs"]}

        # invoke: run the real long-tail verb against the installed binary.
        invoked = data_of(await client.call_tool("invoke", {"verb": "vault list"}))
        assert invoked["ok"] is True
        assert invoked["format"] == "json"
        assert invoked["command"][0] == "vaultspec-core"


async def test_surface_whole_call_failure_is_iserror(vault_root):  # noqa: F811
    """A whole-call failure raises to protocol ``isError``, not a success dict."""
    mcp = create_server()
    async with create_connected_server_and_client_session(mcp) as client:
        empty_create = await client.call_tool("create", {"documents": []})
        assert empty_create.isError
        unknown_verb = await client.call_tool("invoke", {"verb": "totally bogus"})
        assert unknown_verb.isError


def test_registry_entry_launches_this_server_unchanged(vault_root):  # noqa: F811
    """The shipped MCP registry entry still launches this server module.

    The builtin registry definition (ADR Q8: installation is a no-op for
    existing projects) must keep pointing at the module whose ``create_server``
    this test drives, so a synced project picks up the nine-tool surface with
    no registry migration.
    """
    registry = vault_root / ".vaultspec" / "mcps" / "vaultspec-core.builtin.json"
    definition = json.loads(registry.read_text(encoding="utf-8"))
    args = definition["args"]
    assert "vaultspec_core.mcp_server.app" in args
    assert args[-1] == "vaultspec_core.mcp_server.app"

    # The module the registry launches exposes the exact bootstrap this test
    # exercised, so the launched process serves the same nine-tool surface.
    from vaultspec_core.mcp_server import app as launched

    assert callable(launched.create_server)
    assert callable(launched.run)
