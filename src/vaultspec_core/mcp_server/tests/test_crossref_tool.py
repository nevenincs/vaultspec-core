"""The ``crossref`` MCP tool over the real server: registration, refusals, parity.

No test here reaches the network: without a key the backend sends nothing,
and every refusal happens before a client exists. The judgment itself is
covered by the crossref package's own tests against a local provider.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest
from mcp import Client
from typer.testing import CliRunner

from vaultspec_core.cli import app
from vaultspec_core.crossref import MAX_SOURCES, CrossrefStatus
from vaultspec_core.mcp_server.app import create_server
from vaultspec_core.search import CREDENTIAL_VARIABLE

from .conftest import data_of

if TYPE_CHECKING:
    from pathlib import Path

    from mcp.types import CallToolResult, Tool

pytestmark = [pytest.mark.unit]

_SOURCE = "2026-02-20-widget-adr"


@pytest.fixture
def adr_root(vault_root: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The installed vault with two ADRs and no hosted-search key anywhere."""
    monkeypatch.delenv(CREDENTIAL_VARIABLE, raising=False)
    for stem in (_SOURCE, "2026-02-21-gadget-adr"):
        path = vault_root / ".vault" / "adr" / f"{stem}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "---\ntags:\n  - '#adr'\n  - '#widget'\ndate: '2026-02-20'\n---\n\n"
            f"# `widget` adr: `{stem}` | (**status:** `accepted`)\n\n"
            "## Problem Statement\n\nWidgets need a store.\n",
            encoding="utf-8",
        )
    return vault_root


def _tool(tools: list[Tool], name: str) -> Tool:
    return next(tool for tool in tools if tool.name == name)


def _error_text(result: CallToolResult) -> str:
    return " ".join(getattr(block, "text", "") for block in result.content)


async def test_the_full_surface_bounds_a_sweep(adr_root: Path) -> None:
    crossref = _tool(await create_server().list_tools(), "crossref")

    properties = crossref.input_schema["properties"]
    assert properties["max_sources"]["maximum"] == MAX_SOURCES
    assert properties["refs"]["maxItems"] == MAX_SOURCES
    assert {"apply", "after", "isolated", "all_adrs", "feature"} <= set(properties)


async def test_the_read_only_surface_judges_one_adr_and_writes_nothing(
    adr_root: Path,
) -> None:
    mcp = create_server(read_only=True)
    crossref = _tool(await mcp.list_tools(), "crossref")

    assert set(crossref.input_schema["properties"]) == {"ref"}
    async with Client(mcp) as client:
        refused = await client.call_tool("crossref", {"ref": _SOURCE, "apply": True})
        judged = data_of(await client.call_tool("crossref", {"ref": _SOURCE}))

    assert refused.is_error
    assert "writes nothing" in _error_text(refused)
    assert judged["sources"][0]["status"] == CrossrefStatus.NOT_CONFIGURED


@pytest.mark.parametrize(
    "arguments",
    [
        {"refs": []},
        {"refs": ["2026-09-09-nothing-adr"]},
        {"all_adrs": True, "max_sources": MAX_SOURCES + 1},
    ],
    ids=["nothing-named", "unknown-adr", "sweep-over-ceiling"],
)
async def test_bad_input_is_refused(adr_root: Path, arguments: dict[str, Any]) -> None:
    async with Client(create_server()) as client:
        result = await client.call_tool("crossref", arguments)

    assert result.is_error, arguments


async def test_without_a_key_the_tool_and_the_cli_return_the_same_reply(
    adr_root: Path,
) -> None:
    async with Client(create_server()) as client:
        payload = data_of(await client.call_tool("crossref", {"refs": [_SOURCE]}))

    runner = CliRunner(env={CREDENTIAL_VARIABLE: ""})
    result = runner.invoke(
        app,
        ["-t", str(adr_root), "vault", "adr", "crossref", _SOURCE, "--json"],
    )
    assert result.exit_code == 0, result.output
    cli = json.loads(result.stdout)["data"]

    (source,) = payload["sources"]
    assert source["status"] == CrossrefStatus.NOT_CONFIGURED
    assert CREDENTIAL_VARIABLE in source["remediation"]
    assert "usage" not in payload
    assert payload == cli
