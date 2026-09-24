"""The ``crossref`` MCP tool over the real server: registration, refusals, parity.

No test here reaches the network. The in-process tests stop before a client
exists: the schema, the read-only guard or the source lookup refuses the call.
The parity tests launch the real server over stdio with an environment that
holds no hosted-search key, so the backend sends nothing. The judgment itself
is covered by the crossref package's own tests against a local provider.
"""

from __future__ import annotations

import dataclasses
import json
import os
from typing import TYPE_CHECKING, Any

import pytest
from mcp import Client
from typer.testing import CliRunner

from vaultspec_core.cli import app
from vaultspec_core.config import VAULTSPEC_CORE_TYPESAFE_API_KEY
from vaultspec_core.core.enums import AdrStatus
from vaultspec_core.crossref import (
    MAX_SOURCES,
    Bounds,
    CrossrefOutcome,
    CrossrefStatus,
    CrossrefUsage,
    SweepOutcome,
    Verdict,
    VerdictKind,
    sweep_fields,
)
from vaultspec_core.mcp_server.app import create_server
from vaultspec_core.mcp_server.envelope import _structured
from vaultspec_core.mcp_server.tools.crossref import (
    CrossrefResult,
    SourceRow,
    _summary,
)

from .conftest import data_of, run_in_fresh_workspace, stdio_session

if TYPE_CHECKING:
    from pathlib import Path

    from mcp.types import CallToolResult, Tool

CREDENTIAL_VARIABLE = VAULTSPEC_CORE_TYPESAFE_API_KEY.env_name

_SOURCE = "2026-02-20-widget-adr"


def _write_adrs(root: Path) -> None:
    """Add two ADRs to the vault at *root*."""
    for stem in (_SOURCE, "2026-02-21-gadget-adr"):
        path = root / ".vault" / "adr" / f"{stem}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "---\ntags:\n  - '#adr'\n  - '#widget'\ndate: '2026-02-20'\n---\n\n"
            f"# `widget` adr: `{stem}` | (**status:** `accepted`)\n\n"
            "## Problem Statement\n\nWidgets need a store.\n",
            encoding="utf-8",
        )


def _tool(tools: list[Tool], name: str) -> Tool:
    return next(tool for tool in tools if tool.name == name)


def _error_text(result: CallToolResult) -> str:
    return " ".join(getattr(block, "text", "") for block in result.content)


@pytest.mark.unit
async def test_the_full_surface_bounds_a_sweep(vault_root: Path) -> None:
    crossref = _tool(await create_server().list_tools(), "crossref")

    properties = crossref.input_schema["properties"]
    assert properties["max_sources"]["maximum"] == MAX_SOURCES
    assert properties["refs"]["maxItems"] == MAX_SOURCES
    assert {"apply", "after", "isolated", "all_adrs", "feature"} <= set(properties)


@pytest.mark.unit
async def test_the_read_only_surface_takes_one_ref_and_refuses_apply(
    vault_root: Path,
) -> None:
    _write_adrs(vault_root)
    mcp = create_server(read_only=True)
    crossref = _tool(await mcp.list_tools(), "crossref")

    assert set(crossref.input_schema["properties"]) == {"ref"}
    async with Client(mcp) as client:
        refused = await client.call_tool("crossref", {"ref": _SOURCE, "apply": True})

    assert refused.is_error
    assert "writes nothing" in _error_text(refused)


@pytest.mark.unit
@pytest.mark.parametrize(
    "arguments",
    [
        {"refs": []},
        {"refs": ["2026-09-09-nothing-adr"]},
        {"all_adrs": True, "max_sources": MAX_SOURCES + 1},
    ],
    ids=["nothing-named", "unknown-adr", "sweep-over-ceiling"],
)
async def test_bad_input_is_refused(
    vault_root: Path, arguments: dict[str, Any]
) -> None:
    _write_adrs(vault_root)
    async with Client(create_server()) as client:
        result = await client.call_tool("crossref", arguments)

    assert result.is_error, arguments


@pytest.mark.unit
def test_a_reply_with_verdicts_reaches_mcp_exactly_as_the_cli_prints_it() -> None:
    verdict = Verdict(
        stem="2026-02-21-gadget-adr",
        title="gadget",
        feature="widget",
        status=None,
        kind=VerdictKind.LINK,
        score=0.61234,
        relation="depends_on",
        declared=False,
    )
    written = dataclasses.replace(
        verdict, stem="2026-02-22-other-adr", status=AdrStatus.ACCEPTED, applied=True
    )
    sweep = SweepOutcome(
        outcomes=(
            CrossrefOutcome(
                source=_SOURCE,
                status=CrossrefStatus.OK,
                verdicts=(verdict, written),
                bounds=Bounds(corpus=3, pool=2, judged=2, unjudged_declared=("x",)),
                usage=CrossrefUsage("jev-1.13.0", 2, 900, 12, 0),
                write_failed=("2026-02-23-broken-adr",),
            ),
        ),
        remaining=4,
        next_after=_SOURCE,
    )
    fields = sweep_fields(sweep)

    assert _structured(CrossrefResult.model_validate(fields)) == fields


@pytest.mark.unit
def test_a_sweep_summary_counts_its_sources_and_names_why_it_stopped() -> None:
    result = CrossrefResult(
        sources=[
            SourceRow(source="a", status="ok", links=2),
            SourceRow(source="b", status="unavailable", reason="content_rejected"),
        ],
        judged=1,
        links=2,
        remaining=3,
        stopped="rate_limited",
    )

    assert _summary(result) == "1 judged, 2 links, 3 remaining, stopped: rate_limited"


def _cli_data(project: Path) -> dict[str, Any]:
    """Run ``vault adr crossref --json`` on *project* without a key."""
    runner = CliRunner(env={CREDENTIAL_VARIABLE: ""})
    result = runner.invoke(
        app, ["-t", str(project), "vault", "adr", "crossref", _SOURCE, "--json"]
    )
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)["data"]


async def _drive_without_a_key(project: Path) -> None:
    _write_adrs(project)
    environ = {k: v for k, v in os.environ.items() if k != CREDENTIAL_VARIABLE}
    async with stdio_session(project, environ=environ) as session:
        await session.initialize()
        payload = data_of(await session.call_tool("crossref", {"refs": [_SOURCE]}))

    (source,) = payload["sources"]
    assert source["status"] == CrossrefStatus.NOT_CONFIGURED
    assert CREDENTIAL_VARIABLE in source["remediation"]
    # Usage is reported whenever a request was made; its absence is the
    # service's statement that nothing was sent.
    assert "usage" not in payload
    # The CLI renders the same backend result under the same keys.
    assert payload == _cli_data(project)

    async with stdio_session(project, "--read-only", environ=environ) as session:
        await session.initialize()
        judged = data_of(await session.call_tool("crossref", {"ref": _SOURCE}))
    assert judged == payload

    async with stdio_session(project, environ=environ) as session:
        await session.initialize()
        swept = data_of(await session.call_tool("crossref", {"all_adrs": True}))
    # The selector reached the backend: both ADRs were selected, none judged.
    assert (swept["judged"], swept["remaining"]) == (0, 2)


@pytest.mark.integration
def test_without_a_key_both_surfaces_return_the_same_reply() -> None:
    run_in_fresh_workspace(_drive_without_a_key, prefix="vsc-mcp-crossref-")
