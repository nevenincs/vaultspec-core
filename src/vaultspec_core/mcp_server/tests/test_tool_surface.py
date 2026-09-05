"""Full ten-tool surface integration test over the real ``create_server``.

Builds the production server through ``create_server`` on a
:class:`WorkspaceFactory`-installed vault and drives it over the in-memory
MCPServer client - no mocks, stubs, or skips. Asserts that exactly the ten
expected tools are registered with the ADR Q6 annotation matrix and an
``outputSchema`` each, exercises a representative call on every tool end-to-end
(including a gateway ``invoke`` of the real ``vault list`` verb), confirms a
whole-call failure surfaces as protocol ``isError``, and checks the shipped MCP
registry entry still launches this same server module unchanged.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from mcp import Client

from vaultspec_core import __version__
from vaultspec_core.mcp_server.app import create_server

from .conftest import data_of, vault_root

__all__ = ["vault_root"]

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]

#: The ten tools the redesigned surface must advertise, and nothing else.
_EXPECTED_TOOLS = frozenset(
    {
        "status",
        "find",
        "create",
        "edit",
        "plan_progress",
        "plan_edit",
        "log",
        "check",
        "discover",
        "invoke",
    }
)

_READ_ONLY_TOOLS = frozenset({"status", "find", "check", "discover"})

#: The ADR Q6 annotation matrix: each tool mapped to the hints it must declare.
#: Read-only tools (status/find/discover) leave ``destructive_hint`` unset
#: (``None``), matching how their :class:`ToolAnnotations` are constructed.
_ANNOTATIONS = {
    "status": {
        "read_only_hint": True,
        "idempotent_hint": True,
        "open_world_hint": False,
    },
    "find": {"read_only_hint": True, "idempotent_hint": True, "open_world_hint": False},
    "discover": {
        "read_only_hint": True,
        "idempotent_hint": True,
        "open_world_hint": False,
    },
    "create": {
        "read_only_hint": False,
        "destructive_hint": False,
        "idempotent_hint": False,
        "open_world_hint": False,
    },
    "edit": {
        "read_only_hint": False,
        "destructive_hint": True,
        "idempotent_hint": False,
        "open_world_hint": False,
    },
    "plan_progress": {
        "read_only_hint": False,
        "destructive_hint": False,
        "idempotent_hint": True,
        "open_world_hint": False,
    },
    "plan_edit": {
        "read_only_hint": False,
        "destructive_hint": True,
        "idempotent_hint": False,
        "open_world_hint": False,
    },
    "log": {
        "read_only_hint": False,
        "destructive_hint": False,
        "idempotent_hint": True,
        "open_world_hint": False,
    },
    "check": {
        "read_only_hint": False,
        "destructive_hint": False,
        "idempotent_hint": True,
        "open_world_hint": False,
    },
    "invoke": {
        "read_only_hint": False,
        "destructive_hint": True,
        "idempotent_hint": False,
        "open_world_hint": False,
    },
}

_READ_ONLY_ANNOTATIONS = {
    "status": {
        "read_only_hint": True,
        "idempotent_hint": True,
        "open_world_hint": False,
    },
    "find": {"read_only_hint": True, "idempotent_hint": True, "open_world_hint": False},
    "check": {
        "read_only_hint": True,
        "idempotent_hint": True,
        "open_world_hint": False,
    },
    "discover": {
        "read_only_hint": True,
        "idempotent_hint": True,
        "open_world_hint": False,
    },
}


async def test_surface_registers_exactly_ten_tools_with_schemas(
    vault_root: Path,
) -> None:
    """``create_server`` advertises exactly the ten tools, schema'd and annotated."""
    mcp = create_server()
    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    assert names == _EXPECTED_TOOLS, names

    by_name = {t.name: t for t in tools}
    for name, expected in _ANNOTATIONS.items():
        tool = by_name[name]
        assert tool.output_schema is not None, f"{name} declares no outputSchema"
        annotations = tool.annotations
        assert annotations is not None, f"{name} declares no annotations"
        for hint, value in expected.items():
            actual = getattr(annotations, hint)
            assert actual == value, f"{name}.{hint} == {actual!r}, expected {value!r}"

    assert "fix" in by_name["check"].input_schema.get("properties", {})


async def test_read_only_surface_omits_mutation_tools_and_repair(
    vault_root: Path,
) -> None:
    """Read-only mode advertises only validation and orientation operations."""
    mcp = create_server(read_only=True)
    tools = await mcp.list_tools()
    names = {tool.name for tool in tools}
    assert names == _READ_ONLY_TOOLS, names

    by_name = {tool.name: tool for tool in tools}
    for name, expected in _READ_ONLY_ANNOTATIONS.items():
        tool = by_name[name]
        assert tool.output_schema is not None, f"{name} declares no outputSchema"
        annotations = tool.annotations
        assert annotations is not None, f"{name} declares no annotations"
        for hint, value in expected.items():
            actual = getattr(annotations, hint)
            assert actual == value, f"{name}.{hint} == {actual!r}, expected {value!r}"

    check_schema = by_name["check"].input_schema
    assert "fix" not in check_schema.get("properties", {})

    async with Client(mcp) as client:
        checked = data_of(await client.call_tool("check", {}))
        rejected_repair = await client.call_tool("check", {"fix": True})
    assert checked["fixed"] is False
    assert rejected_repair.is_error


async def test_surface_instructions_name_the_tools_and_version(
    vault_root: Path,
) -> None:
    """The server instructions string names the surface and carries the version."""
    mcp = create_server()
    instructions = mcp.instructions or ""
    assert __version__ in instructions
    for name in _EXPECTED_TOOLS:
        assert name in instructions, f"{name} missing from instructions"


async def test_surface_representative_call_per_tool(vault_root: Path) -> None:
    """Every tool answers a representative call end-to-end on the real server."""
    mcp = create_server()
    async with Client(mcp) as client:
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
        searched = data_of(await client.call_tool("find", {"feature": "surface-probe"}))
        assert searched and all(row.get("blob_hash") for row in searched), searched

        # status: project rollup and a targeted trace.
        rollup = data_of(await client.call_tool("status", {}))
        assert rollup["kind"] == "rollup"
        assert rollup["tool_schema_version"] == __version__
        trace = data_of(await client.call_tool("status", {"target": "surface-probe"}))
        assert trace["kind"] == "trace"

        # check: run the health suite over the vault.
        checked = data_of(await client.call_tool("check", {"fix": True}))
        assert checked["status"] in {"ok", "failed"}
        assert "checks" in checked
        assert checked["fixed"] is True

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


async def test_surface_whole_call_failure_is_iserror(vault_root: Path) -> None:
    """A whole-call failure raises to protocol ``isError``, not a success dict."""
    mcp = create_server()
    async with Client(mcp) as client:
        empty_create = await client.call_tool("create", {"documents": []})
        assert empty_create.is_error
        unknown_verb = await client.call_tool("invoke", {"verb": "totally bogus"})
        assert unknown_verb.is_error


def test_registry_entry_launches_this_server_unchanged(vault_root: Path) -> None:
    """The shipped MCP registry entry still launches this server module.

    The builtin registry definition (ADR Q8: installation is a no-op for
    existing projects) must keep resolving to the module whose
    ``create_server`` this test drives, so a synced project picks up the
    ten-tool surface with no registry migration. Since the install-mode
    model, the seeded registry carries the mode-neutral launch tokens and
    the concrete launch is rendered per install mode; every mode must still
    target this server module.
    """
    from vaultspec_core.core.enums import InstallMode
    from vaultspec_core.core.mcps import render_mcp_definition_for_mode

    registry = vault_root / ".vaultspec" / "mcps" / "vaultspec-core.builtin.json"
    definition = json.loads(registry.read_text(encoding="utf-8"))
    assert definition["args"] == ["@@VAULTSPEC_INSTALL_MODE_ARGS@@"]

    for mode in (InstallMode.TOOL, InstallMode.DEPENDENCY, InstallMode.DEV):
        rendered = render_mcp_definition_for_mode(definition, mode)
        assert rendered["args"][-1] == "vaultspec_core.mcp_server.app", mode

    # The module the registry launches exposes the exact bootstrap this test
    # exercised, so the launched process serves the same ten-tool surface.
    from vaultspec_core.mcp_server import app as launched

    assert callable(launched.create_server)
    assert callable(launched.run)


async def test_tool_list_is_invariant_under_companion_presence(
    vault_root: Path,
) -> None:
    """Core's advertised tools never vary with whether rag is provisioned.

    The rejected design was conditional registration - advertise search tools
    when rag is detected, hide them when it is not. It fails on two counts
    this test pins. A host caches the tool list at connect, so a rag installed
    or removed mid-session leaves the host confidently wrong in both
    directions. And core's tool surface would stop being a function of core's
    version: two workspaces on the same core would present different APIs,
    which is the precise reproducibility property the install-mode machinery
    exists to guarantee.

    Both companion states are built through core's own launch renderer rather
    than a hand-written argv, so the fixture cannot drift from what core
    actually deploys.
    """
    from vaultspec_core.core.diagnosis.collectors_companion import (
        RAG_DISTRIBUTION_NAME,
    )
    from vaultspec_core.core.enums import InstallMode
    from vaultspec_core.core.mcps_mode import render_launch_for_mode

    mcp_path = vault_root / ".mcp.json"

    async def _names_now() -> frozenset[str]:
        return frozenset(t.name for t in await create_server().list_tools())

    original = mcp_path.read_text(encoding="utf-8") if mcp_path.exists() else None

    without_rag = await _names_now()

    command, args = render_launch_for_mode(
        InstallMode.TOOL,
        RAG_DISTRIBUTION_NAME,
        "vaultspec_rag.server",
        tool_spec=f"{RAG_DISTRIBUTION_NAME}[mcp]",
    )
    config: dict[str, Any] = json.loads(original) if original else {}
    servers: dict[str, Any] = config.setdefault("mcpServers", {})
    servers[RAG_DISTRIBUTION_NAME] = {"command": command, "args": args}
    mcp_path.write_text(json.dumps(config), encoding="utf-8")

    try:
        with_rag = await _names_now()
    finally:
        if original is None:
            mcp_path.unlink(missing_ok=True)
        else:
            mcp_path.write_text(original, encoding="utf-8")

    assert with_rag == without_rag, (
        "core's tool list changed with rag's presence; the surface must be a "
        "pure function of core's version"
    )
    assert with_rag == _EXPECTED_TOOLS
    assert not any("search" in name for name in with_rag), (
        "core must not advertise a search tool; semantic search stays on "
        "rag's own MCP channel"
    )
