"""Tests for the MCP ``search`` tool.

Four concerns, each against real code. The projection from a search outcome
to the wire is tested from constructed outcomes, because it is pure. Input
validation runs on the real in-memory server, since every refusal happens
before a credential is resolved and so does not depend on the environment. The
no-key path runs the real server as a stdio subprocess with an environment the
test controls, because an in-process server would read the ambient one. The
reply budget is measured on the worst-case wire payload, built by the search
package's own bounding from text in the scripts that cost the most bytes.

A configured search needs the network and a key; the search package's own
tests and its deselected live test cover that path.
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any

import pytest
from mcp import Client
from mcp.types import CallToolResult
from typer.testing import CliRunner

from vaultspec_core.cli import app
from vaultspec_core.config import VAULTSPEC_CORE_TYPESAFE_API_KEY, CredentialSource
from vaultspec_core.core.diagnosis.collectors_companion import (
    RAG_DISTRIBUTION_NAME,
    CompanionSignal,
)
from vaultspec_core.core.discovery_guidance import LIST_VAULT, RAG_VAULT_SEARCH
from vaultspec_core.core.enums import InstallMode
from vaultspec_core.core.mcps_mode import render_launch_for_mode
from vaultspec_core.core.windowing import apply_window
from vaultspec_core.mcp_server.app import create_server
from vaultspec_core.mcp_server.envelope import compact_result
from vaultspec_core.mcp_server.tools.search import (
    SearchResult,
    _search_summary,
    search_result,
)
from vaultspec_core.search import (
    DEFAULT_RESULTS,
    EXCERPT_BYTES,
    MAX_QUERY_CHARS,
    MAX_RESULTS,
    SEARCHABLE_TYPES,
    Excerpt,
    NextStep,
    NextStepKind,
    SearchHit,
    SearchOutcome,
    SearchStatus,
    SearchUsage,
    SearchVerdict,
    UnavailableReason,
    hit_fields,
    outcome_fields,
    unscored_note,
)
from vaultspec_core.search.tests.reply_budget import (
    DISCOVERY_BUDGET,
    ENVELOPE_BYTES_PER_TOKEN,
    REPLY_CEILING,
    WORST_SHAPES,
    worst_case_ranking,
)
from vaultspec_core.vaultcore.models import DocType

from .conftest import data_of, run_in_fresh_workspace, stdio_session

if TYPE_CHECKING:
    from pathlib import Path

    from mcp.types import Tool

#: The next step a workspace without rag resolves to for an unfiltered search.
_LISTING = NextStep(
    kind=NextStepKind.LISTING, types=tuple(SEARCHABLE_TYPES), command=LIST_VAULT
)

#: A stand-in credential. It never reaches the network: the only call made
#: with it set is ``status``, which reads configuration and sends nothing.
_SENTINEL_KEY = "vsc-sentinel-credential-0123456789"


def _excerpt(
    text: str, section: str = "Constraints", *, truncated: bool = False
) -> Excerpt:
    return Excerpt(
        section=section,
        line_start=40,
        line_end=40 + text.count("\n"),
        text=text,
        truncated=truncated,
    )


def _hit(
    index: int = 0,
    *,
    excerpt: Excerpt | None = None,
    supporting: Excerpt | None = None,
    stem: str = "2026-01-02-widget-adr",
    title: str = "Widget storage",
    feature: str = "widget",
) -> SearchHit:
    return SearchHit(
        name=f"{stem}{index or ''}",
        path=f".vault/adr/{stem}{index or ''}.md",
        doc_type=DocType.ADR,
        feature=feature,
        date="2026-09-23",
        title=title,
        score=0.912345,
        answers=0.876543,
        premise_conflict=0.012345,
        excerpt=excerpt,
        supporting=supporting,
        blob_hash="0123456789abcdef0123456789abcdef01234567",
    )


def _ranked(
    hits: list[SearchHit],
    *,
    limit: int = DEFAULT_RESULTS,
    answered: bool = True,
    unscored: int = 0,
) -> SearchOutcome:
    """Build an ``ok`` outcome paged exactly as the service pages a ranking."""
    page, window = apply_window(hits, limit=limit, pageable=False)
    return SearchOutcome(
        status=SearchStatus.OK,
        query="Why does the discovery budget stop at 4,000 tokens?",
        answered=answered,
        hits=tuple(page),
        window=window,
        usage=SearchUsage(
            model="jev-1.13.0",
            requests=6,
            input_tokens=41_250,
            elapsed_ms=1_235,
            unscored=unscored,
        ),
    )


async def _reply(outcome: SearchOutcome) -> CallToolResult:
    """Render *outcome* as the ``search`` tool puts it on the wire."""

    async def tool() -> SearchResult:
        return search_result(outcome)

    # The envelope keeps the declared return type for the output schema and
    # returns the wire object itself at runtime.
    wire: object = await compact_result(_search_summary)(tool)()
    assert isinstance(wire, CallToolResult)
    return wire


def _summary(reply: CallToolResult) -> str:
    return "".join(getattr(block, "text", "") for block in reply.content)


# ---------------------------------------------------------------------------
# Projection
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_excerpts_travel_as_the_search_bounded_them() -> None:
    # The search package cuts and marks excerpts; the wire carries its text,
    # range and marker unchanged rather than clipping a second time.
    answer = "\n".join(f"Line {i:02d} of the answering block." for i in range(60))
    support = "The ceiling is 10,000 tokens per reply."
    assert len(answer.encode("utf-8")) > EXCERPT_BYTES

    row = search_result(
        _ranked(
            [
                _hit(
                    excerpt=_excerpt(answer),
                    supporting=_excerpt(support, truncated=True),
                )
            ]
        )
    ).hits[0]

    assert row.excerpt is not None
    assert row.supporting is not None
    assert (row.excerpt.text, row.excerpt.truncated) == (answer, False)
    assert (row.excerpt.line_start, row.excerpt.line_end) == (40, 99)
    assert (row.supporting.text, row.supporting.truncated) == (support, True)


@pytest.mark.unit
def test_a_hit_carries_its_locators_and_rounded_scores() -> None:
    row = search_result(_ranked([_hit()])).hits[0]

    assert row.path == ".vault/adr/2026-01-02-widget-adr.md"
    assert row.type == DocType.ADR.value
    assert (row.score, row.answers, row.premise_conflict) == (0.912, 0.877, 0.012)


@pytest.mark.unit
async def test_a_hit_travels_as_the_search_package_projects_it() -> None:
    # One projection serves every surface, so the CLI's --json hits and these
    # carry the same keys and the same rounding.
    hit = _hit(excerpt=_excerpt("The answer.", truncated=True))

    reply = await _reply(_ranked([hit]))

    payload = reply.structured_content
    assert payload is not None
    assert payload["hits"] == [hit_fields(hit)]
    # A workspace locator would grow each hit with the root's length.
    assert "resource_uri" not in payload["hits"][0]


@pytest.mark.unit
async def test_the_wire_omits_absent_excerpts_the_query_and_the_name() -> None:
    reply = await _reply(_ranked([_hit()]))

    payload = reply.structured_content
    assert payload is not None
    hit = payload["hits"][0]
    assert "excerpt" not in hit
    assert "supporting" not in hit
    # The caller sent the query and the name is the path's stem: neither is
    # carried back.
    assert "query" not in payload
    assert "name" not in hit


@pytest.mark.unit
async def test_a_capped_page_reports_its_window_without_an_offset() -> None:
    ranking = [_hit(i) for i in range(DEFAULT_RESULTS + 3)]

    reply = await _reply(_ranked(ranking))

    payload = reply.structured_content
    assert payload is not None
    assert payload["returned"] == DEFAULT_RESULTS
    assert payload["total"] == DEFAULT_RESULTS + 3
    assert payload["truncated"] is True
    # A ranking is recomputed per request, so there is nothing to resume.
    assert "next_offset" not in payload
    assert "offset" not in payload
    assert (
        _summary(reply) == f"{DEFAULT_RESULTS} of {DEFAULT_RESULTS + 3} hits, answered"
    )


@pytest.mark.unit
async def test_an_unanswered_whole_page_says_so() -> None:
    reply = await _reply(_ranked([_hit()], answered=False))

    payload = reply.structured_content
    assert payload is not None
    assert payload["answered"] is False
    assert payload["verdict"] == SearchVerdict.NOTHING_ANSWERS.value
    assert payload["truncated"] is False
    assert _summary(reply) == f"1 hit, {SearchVerdict.NOTHING_ANSWERS.sentence}"


@pytest.mark.unit
@pytest.mark.parametrize(
    "outcome",
    [
        _ranked([_hit(excerpt=_excerpt("The answer."))], unscored=1),
        SearchOutcome(
            status=SearchStatus.NOT_CONFIGURED, query="q", next_step=_LISTING
        ),
        SearchOutcome(
            status=SearchStatus.UNAVAILABLE,
            query="q",
            reason=UnavailableReason.DEADLINE,
            usage=SearchUsage("jev-1.13.0", 3, 900, 25_000, 0),
            next_step=_LISTING,
        ),
    ],
    ids=["ok", "not-configured", "unavailable"],
)
async def test_the_wire_is_the_search_packages_one_projection(
    outcome: SearchOutcome,
) -> None:
    # The CLI's --json data is this same projection, so the two surfaces carry
    # the same keys and values for every outcome.
    reply = await _reply(outcome)

    assert reply.structured_content == json.loads(json.dumps(outcome_fields(outcome)))


@pytest.mark.unit
async def test_the_summary_counts_records_left_unscored() -> None:
    reply = await _reply(_ranked([_hit()], answered=False, unscored=2))

    payload = reply.structured_content
    assert payload is not None
    assert payload["usage"]["unscored"] == 2
    # The page's own verdict, then the note the CLI prints, word for word.
    verdict = SearchVerdict.NONE_READ_ANSWERS.sentence
    assert _summary(reply) == f"1 hit, {verdict}, {unscored_note(2)}"


@pytest.mark.unit
async def test_not_configured_names_the_variable_and_the_next_step() -> None:
    outcome = SearchOutcome(
        status=SearchStatus.NOT_CONFIGURED, query="q", next_step=_LISTING
    )

    reply = await _reply(outcome)

    payload = reply.structured_content
    assert payload is not None
    assert payload["status"] == SearchStatus.NOT_CONFIGURED.value
    assert payload["answered"] is False
    assert payload["hits"] == []
    assert payload["next_step"] == {
        "kind": NextStepKind.LISTING.value,
        "types": sorted(SEARCHABLE_TYPES),
        "command": LIST_VAULT,
    }
    remediation = payload["remediation"]
    assert VAULTSPEC_CORE_TYPESAFE_API_KEY.env_name in remediation
    assert f"`{LIST_VAULT}`" in remediation
    # Nothing ranked and nothing sent: no window, verdict or usage to report.
    for absent in ("returned", "total", "truncated", "usage", "reason", "verdict"):
        assert absent not in payload, absent
    assert _summary(reply) == "not configured"


@pytest.mark.unit
@pytest.mark.parametrize("reason", list(UnavailableReason))
async def test_unavailable_reports_its_reason_and_a_next_step(
    reason: UnavailableReason,
) -> None:
    outcome = SearchOutcome(
        status=SearchStatus.UNAVAILABLE, query="q", reason=reason, next_step=_LISTING
    )

    reply = await _reply(outcome)

    payload = reply.structured_content
    assert payload is not None
    assert payload["status"] == SearchStatus.UNAVAILABLE.value
    assert payload["reason"] == reason.value
    assert payload["next_step"]["kind"] == NextStepKind.LISTING.value
    assert f"`{LIST_VAULT}`" in payload["remediation"]
    assert payload["hits"] == []
    assert _summary(reply) == f"unavailable ({reason.value})"


# ---------------------------------------------------------------------------
# The real server, in memory
# ---------------------------------------------------------------------------


def _error_text(result: CallToolResult) -> str:
    return " ".join(getattr(block, "text", "") for block in result.content)


@pytest.mark.unit
@pytest.mark.parametrize(
    "arguments",
    [
        {"query": ""},
        {"query": "q" * (MAX_QUERY_CHARS + 1)},
        {"query": "q", "limit": 0},
        {"query": "q", "limit": MAX_RESULTS + 1},
        {"query": "q", "type": ["adrs"]},
    ],
    ids=["empty", "overlong", "limit-zero", "limit-over-ceiling", "unknown-type"],
)
async def test_the_schema_refuses_out_of_bounds_input(
    vault_root: Path, arguments: dict[str, Any]
) -> None:
    async with Client(create_server()) as client:
        result = await client.call_tool("search", arguments)

    assert result.is_error, arguments


@pytest.mark.unit
async def test_a_blank_query_is_refused_with_the_service_reason(
    vault_root: Path,
) -> None:
    async with Client(create_server()) as client:
        result = await client.call_tool("search", {"query": "   "})

    assert result.is_error
    assert "blank" in _error_text(result)


@pytest.mark.unit
async def test_an_unsearchable_type_is_refused_not_answered_from_nothing(
    vault_root: Path,
) -> None:
    async with Client(create_server()) as client:
        result = await client.call_tool(
            "search", {"query": "q", "type": [DocType.ADR.value, DocType.INDEX.value]}
        )

    assert result.is_error
    text = _error_text(result)
    assert DocType.INDEX.value in text
    for searchable in SEARCHABLE_TYPES:
        assert searchable.value in text


def _tool(tools: list[Tool], name: str) -> Tool:
    return next(tool for tool in tools if tool.name == name)


@pytest.mark.unit
@pytest.mark.parametrize("read_only", [False, True], ids=["full", "read-only"])
async def test_search_is_registered_with_its_bounds_on_both_surfaces(
    vault_root: Path, read_only: bool
) -> None:
    search = _tool(await create_server(read_only=read_only).list_tools(), "search")

    annotations = search.annotations
    assert annotations is not None
    assert annotations.read_only_hint is True
    assert annotations.idempotent_hint is True
    assert annotations.open_world_hint is True
    assert annotations.destructive_hint is None

    properties = search.input_schema["properties"]
    assert search.input_schema["required"] == ["query"]
    assert properties["query"]["maxLength"] == MAX_QUERY_CHARS
    assert properties["limit"]["maximum"] == MAX_RESULTS
    assert properties["limit"]["default"] == DEFAULT_RESULTS
    # The filter offers exactly the types search ranks, never one it refuses.
    assert properties["type"]["items"]["enum"] == [
        doc_type.value for doc_type in DocType if doc_type in SEARCHABLE_TYPES
    ]
    assert DocType.INDEX.value not in properties["type"]["items"]["enum"]


@pytest.mark.unit
async def test_the_output_schema_describes_the_domain_shapes_leanly(
    vault_root: Path,
) -> None:
    search = _tool(await create_server().list_tools(), "search")
    schema = search.output_schema
    assert schema is not None

    # A shape used twice is described once and referenced; a shape used once
    # is inlined where it is used.
    hit = schema["properties"]["hits"]["items"]["properties"]
    assert hit["excerpt"] == hit["supporting"] == {"$ref": "#/$defs/Excerpt"}
    assert list(schema["$defs"]) == [Excerpt.__name__]
    shapes = {
        Excerpt: schema["$defs"][Excerpt.__name__],
        SearchUsage: schema["properties"]["usage"],
        NextStep: schema["properties"]["next_step"],
    }
    for shape, definition in shapes.items():
        fields = list(shape.__dataclass_fields__)
        # Every field is always serialised, so every field is required, and
        # the maintainer docstring and derived titles stay off the wire.
        assert definition["required"] == fields
        assert "description" not in definition
        assert "title" not in definition
        for prop in definition["properties"].values():
            assert "title" not in prop
            assert "default" not in prop
    assert shapes[SearchUsage]["properties"]["elapsed_ms"]["type"] == "integer"
    # An enum field of a shape ships as its values, with no definition of its own.
    assert shapes[NextStep]["properties"]["kind"] == {
        "enum": [kind.value for kind in NextStepKind],
        "type": "string",
    }
    assert NextStepKind.__name__ not in schema["$defs"]
    # A result is never input, so none of its properties carries a default.
    assert all("default" not in prop for prop in schema["properties"].values())


@pytest.mark.unit
async def test_find_and_search_share_one_declaration_of_each_filter(
    vault_root: Path,
) -> None:
    tools = await create_server().list_tools()
    find = _tool(tools, "find").input_schema["properties"]
    search = _tool(tools, "search").input_schema["properties"]

    assert find["feature"] == search["feature"]
    assert find["date"] == search["date"]
    # Find lists every record type; search lists the ones it ranks.
    assert find["type"]["items"]["enum"] == [doc_type.value for doc_type in DocType]
    assert search["type"]["items"]["enum"] == [
        doc_type.value for doc_type in DocType if doc_type in SEARCHABLE_TYPES
    ]
    # The type descriptions differ only in the default each tool applies.
    assert find["type"]["description"] != search["type"]["description"]

    async with Client(create_server()) as client:
        refused = await client.call_tool("find", {"type": ["adrs"]})
    assert refused.is_error


# ---------------------------------------------------------------------------
# The real server, over stdio, with a controlled environment
# ---------------------------------------------------------------------------


_QUESTION = "Why does discovery stop at 4,000 tokens?"


def _cli_search_data(project: Path, *args: str) -> dict[str, Any]:
    """Run ``vault search --json`` on *project* without a key; return its data."""
    runner = CliRunner(env={VAULTSPEC_CORE_TYPESAFE_API_KEY.env_name: ""})
    result = runner.invoke(
        app, ["-t", str(project), "vault", "search", _QUESTION, *args, "--json"]
    )
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)["data"]


def _cli_status_data(project: Path) -> dict[str, Any]:
    """Run ``status --json`` on *project* without a key; return its data."""
    runner = CliRunner(env={VAULTSPEC_CORE_TYPESAFE_API_KEY.env_name: ""})
    result = runner.invoke(app, ["-t", str(project), "status", "--json"])
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)["data"]


def _provision_rag(project: Path) -> None:
    """Add the ``.mcp.json`` entry core renders for a tool-mode rag."""
    mcp_json = project / ".mcp.json"
    config = json.loads(mcp_json.read_text(encoding="utf-8"))
    command, args = render_launch_for_mode(
        InstallMode.TOOL,
        RAG_DISTRIBUTION_NAME,
        "vaultspec_rag.server",
        tool_spec=f"{RAG_DISTRIBUTION_NAME}[mcp]",
    )
    config["mcpServers"][RAG_DISTRIBUTION_NAME] = {"command": command, "args": args}
    mcp_json.write_text(json.dumps(config), encoding="utf-8")


async def _drive_without_a_key(project: Path) -> None:
    environ = {
        k: v
        for k, v in os.environ.items()
        if k != VAULTSPEC_CORE_TYPESAFE_API_KEY.env_name
    }
    async with stdio_session(project, environ=environ) as session:
        await session.initialize()

        payload = data_of(await session.call_tool("search", {"query": _QUESTION}))
        assert payload["status"] == SearchStatus.NOT_CONFIGURED.value
        assert payload["answered"] is False
        assert payload["hits"] == []
        # Usage is reported whenever a request was made; its absence is the
        # service's statement that nothing was sent.
        assert "usage" not in payload
        assert VAULTSPEC_CORE_TYPESAFE_API_KEY.env_name in payload["remediation"]
        assert payload["next_step"]["kind"] == NextStepKind.LISTING.value
        # The CLI renders the same backend result under the same keys.
        assert payload == _cli_search_data(project)

        _provision_rag(project)
        payload = data_of(
            await session.call_tool("search", {"query": _QUESTION, "type": ["adr"]})
        )
        assert payload["next_step"] == {
            "kind": NextStepKind.RAG_SEARCH.value,
            "types": ["adr"],
            "command": f"{RAG_VAULT_SEARCH} --doc-type adr",
        }
        assert payload == _cli_search_data(project, "--type", "adr")

        # Both status surfaces carry the backend's discovery record, the same
        # keys ``status --json`` carries, including the rag provisioning.
        status = data_of(await session.call_tool("status", {}))
        assert status["hosted_search"] == {"configured": False, "source": None}
        assert status["companion"]["package"] == RAG_DISTRIBUTION_NAME
        assert status["companion"]["signal"] != CompanionSignal.ABSENT.value
        cli = _cli_status_data(project)
        for key in ("hosted_search", "companion"):
            assert status[key] == cli[key], key


async def _drive_with_a_key(project: Path) -> None:
    environ = {**os.environ, VAULTSPEC_CORE_TYPESAFE_API_KEY.env_name: _SENTINEL_KEY}
    async with stdio_session(project, environ=environ) as session:
        await session.initialize()

        result = await session.call_tool("status", {})
        status = data_of(result)
        assert status["hosted_search"] == {
            "configured": True,
            "source": CredentialSource.ENVIRONMENT.value,
        }
        assert _SENTINEL_KEY not in result.model_dump_json()


@pytest.mark.integration
def test_without_a_key_search_reports_not_configured_and_sends_nothing() -> None:
    run_in_fresh_workspace(_drive_without_a_key, prefix="vsc-mcp-search-")


@pytest.mark.integration
def test_status_reports_a_configured_key_by_source_never_by_value() -> None:
    run_in_fresh_workspace(_drive_with_a_key, prefix="vsc-mcp-search-key-")


# ---------------------------------------------------------------------------
# Reply budget
# ---------------------------------------------------------------------------


async def _reply_tokens(shape: str, limit: int) -> float:
    ranking = worst_case_ranking(shape)
    reply = await _reply(_ranked(ranking, limit=limit, answered=False, unscored=99))

    payload = reply.structured_content
    assert payload is not None
    assert len(payload["hits"]) == limit
    wire = reply.model_dump_json(by_alias=True, exclude_none=True).encode("utf-8")
    return len(wire) / ENVELOPE_BYTES_PER_TOKEN


@pytest.mark.unit
@pytest.mark.parametrize("shape", list(WORST_SHAPES))
async def test_a_default_worst_case_reply_fits_the_discovery_budget(
    shape: str,
) -> None:
    tokens = await _reply_tokens(shape, DEFAULT_RESULTS)

    assert tokens <= DISCOVERY_BUDGET, (
        f"{DEFAULT_RESULTS} worst-case {shape} hits cost {tokens:,.0f} tokens"
    )


@pytest.mark.unit
@pytest.mark.parametrize("shape", list(WORST_SHAPES))
async def test_a_full_worst_case_reply_fits_the_reply_ceiling(shape: str) -> None:
    tokens = await _reply_tokens(shape, MAX_RESULTS)

    assert tokens <= REPLY_CEILING, (
        f"{MAX_RESULTS} worst-case {shape} hits cost {tokens:,.0f} tokens"
    )
