"""Tests for the MCP ``search`` tool.

Four concerns, each against real code. The projection from a search outcome
to the wire is tested from constructed outcomes, because it is pure. Input
validation runs on the real in-memory server, since every refusal happens
before a credential is resolved and so does not depend on the environment. The
no-key path runs the real server as a stdio subprocess with an environment the
test controls, because an in-process server would read the ambient one. The
reply budget is measured on the worst-case wire payload.

A configured search needs the network and a key; the search package's own
tests and its deselected live test cover that path.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from mcp import Client
from mcp.types import CallToolResult

from vaultspec_core.core.discovery_guidance import SEARCH_ADR
from vaultspec_core.core.windowing import apply_window
from vaultspec_core.mcp_server.app import create_server
from vaultspec_core.mcp_server.envelope import compact_result
from vaultspec_core.mcp_server.tools.search import (
    SearchResult,
    _search_summary,
    search_result,
)
from vaultspec_core.search import (
    CREDENTIAL_VARIABLE,
    DEFAULT_RESULTS,
    EXCERPT_CHARS,
    MAX_QUERY_CHARS,
    MAX_RESULTS,
    SEARCHABLE_TYPES,
    SUPPORTING_CHARS,
    CredentialSource,
    Excerpt,
    SearchHit,
    SearchOutcome,
    SearchStatus,
    SearchUsage,
    UnavailableReason,
)
from vaultspec_core.search._corpus import SECTION_CHARS, TITLE_CHARS
from vaultspec_core.vaultcore.models import DocType

from .conftest import data_of, run_in_fresh_workspace, stdio_session

if TYPE_CHECKING:
    from mcp.types import Tool

#: A workspace root the projected ``resource_uri`` values are built on.
_ROOT = Path(tempfile.gettempdir()).resolve() / "workspaces" / "search-project"

#: Bytes of reply JSON per token, as the envelope budgets are measured.
_BYTES_PER_TOKEN = 3.46

#: The discovery reply budget, in tokens, that a default search must fit.
_DISCOVERY_BUDGET = 4_000

#: The ceiling no single reply may exceed, in tokens, whatever the limit.
_REPLY_CEILING = 10_000

#: A stand-in credential. It never reaches the network: the only call made
#: with it set is ``status``, which reads configuration and sends nothing.
_SENTINEL_KEY = "vsc-sentinel-credential-0123456789"


def _excerpt(text: str, section: str = "Constraints") -> Excerpt:
    return Excerpt(
        section=section,
        line_start=40,
        line_end=40 + text.count("\n"),
        text=text,
    )


def _hit(
    index: int = 0,
    *,
    excerpt: Excerpt | None = None,
    supporting: Excerpt | None = None,
    stem: str = "2026-09-23-search-adr",
    title: str = "Hosted vault search",
    feature: str = "search",
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
    hits: list[SearchHit], *, limit: int = DEFAULT_RESULTS, answered: bool = True
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
            elapsed_ms=1_234.567,
            unscored=0,
        ),
    )


async def _reply(outcome: SearchOutcome) -> CallToolResult:
    """Render *outcome* as the ``search`` tool puts it on the wire."""

    async def tool() -> SearchResult:
        return search_result(outcome, _ROOT)

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
def test_an_excerpt_over_its_cap_is_cut_at_a_line_boundary_and_marked() -> None:
    lines = [
        f"Line {i:02d} of the answering block, long enough to matter."
        for i in range(40)
    ]
    text = "\n".join(lines)
    assert len(text) > EXCERPT_CHARS

    row = search_result(_ranked([_hit(excerpt=_excerpt(text))]), _ROOT).hits[0]

    assert row.excerpt is not None
    carried = row.excerpt.text
    assert row.excerpt.truncated is True
    assert len(carried) <= EXCERPT_CHARS
    assert text.startswith(carried)
    assert text[len(carried)] == "\n", "the cut must fall on a line boundary"
    # The line range still locates the whole block, so the rest is one read away.
    assert (row.excerpt.line_start, row.excerpt.line_end) == (40, 79)


@pytest.mark.unit
def test_supporting_text_is_bounded_by_its_own_cap() -> None:
    answer = "The ceiling is 10,000 tokens per reply."
    support = "\n".join(f"Supporting line {i:02d} with more detail." for i in range(30))
    assert len(support) > SUPPORTING_CHARS

    row = search_result(
        _ranked([_hit(excerpt=_excerpt(answer), supporting=_excerpt(support))]), _ROOT
    ).hits[0]

    assert row.excerpt is not None
    assert row.supporting is not None
    assert (row.excerpt.text, row.excerpt.truncated) == (answer, False)
    assert row.supporting.truncated is True
    assert len(row.supporting.text) <= SUPPORTING_CHARS
    assert support.startswith(row.supporting.text)


@pytest.mark.unit
def test_a_hit_carries_its_locators_and_rounded_scores() -> None:
    row = search_result(_ranked([_hit()]), _ROOT).hits[0]

    assert row.path == ".vault/adr/2026-09-23-search-adr.md"
    assert row.type == DocType.ADR.value
    assert row.resource_uri == (_ROOT / row.path).as_uri()
    assert (row.score, row.answers, row.premise_conflict) == (0.912, 0.877, 0.012)


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
    assert payload["truncated"] is False
    assert _summary(reply) == "1 hit, not answered"


@pytest.mark.unit
async def test_not_configured_names_the_variable_and_the_rag_fallback() -> None:
    outcome = SearchOutcome(status=SearchStatus.NOT_CONFIGURED, query="q")

    reply = await _reply(outcome)

    payload = reply.structured_content
    assert payload is not None
    assert payload["status"] == SearchStatus.NOT_CONFIGURED.value
    assert payload["hits"] == []
    remediation = payload["remediation"]
    assert CREDENTIAL_VARIABLE in remediation
    assert SEARCH_ADR in remediation
    # Nothing ranked and nothing sent: no window and no usage to report.
    for absent in ("returned", "total", "truncated", "usage", "reason"):
        assert absent not in payload, absent
    assert _summary(reply) == "not configured"


@pytest.mark.unit
@pytest.mark.parametrize("reason", list(UnavailableReason))
async def test_unavailable_reports_its_reason_and_a_next_step(
    reason: UnavailableReason,
) -> None:
    outcome = SearchOutcome(status=SearchStatus.UNAVAILABLE, query="q", reason=reason)

    reply = await _reply(outcome)

    payload = reply.structured_content
    assert payload is not None
    assert payload["status"] == SearchStatus.UNAVAILABLE.value
    assert payload["reason"] == reason.value
    assert SEARCH_ADR in payload["remediation"]
    assert payload["hits"] == []
    assert _summary(reply) == f"unavailable: {reason.value}"


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
    for searchable in SEARCHABLE_TYPES:
        assert searchable.value in properties["type"]["description"]


@pytest.mark.unit
async def test_find_and_search_share_one_declaration_of_each_filter(
    vault_root: Path,
) -> None:
    tools = await create_server().list_tools()
    find = _tool(tools, "find").input_schema["properties"]
    search = _tool(tools, "search").input_schema["properties"]

    assert find["feature"] == search["feature"]
    assert find["date"] == search["date"]
    for properties in (find, search):
        items = properties["type"]["anyOf"][0]["items"]
        assert items["enum"] == [doc_type.value for doc_type in DocType]
    # The type descriptions differ only in the default each tool applies.
    assert find["type"]["description"] != search["type"]["description"]

    async with Client(create_server()) as client:
        refused = await client.call_tool("find", {"type": ["adrs"]})
    assert refused.is_error


# ---------------------------------------------------------------------------
# The real server, over stdio, with a controlled environment
# ---------------------------------------------------------------------------


async def _drive_without_a_key(project: Path) -> None:
    environ = {k: v for k, v in os.environ.items() if k != CREDENTIAL_VARIABLE}
    async with stdio_session(project, environ=environ) as session:
        await session.initialize()

        payload = data_of(
            await session.call_tool(
                "search", {"query": "Why does discovery stop at 4,000 tokens?"}
            )
        )
        assert payload["status"] == SearchStatus.NOT_CONFIGURED.value
        assert payload["hits"] == []
        # Usage is reported whenever a request was made; its absence is the
        # service's statement that nothing was sent.
        assert "usage" not in payload
        assert CREDENTIAL_VARIABLE in payload["remediation"]
        assert SEARCH_ADR in payload["remediation"]

        status = data_of(await session.call_tool("status", {}))
        assert status["hosted_search"] == {"configured": False}


async def _drive_with_a_key(project: Path) -> None:
    environ = {**os.environ, CREDENTIAL_VARIABLE: _SENTINEL_KEY}
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

#: Stems, feature tags and heading depth sized to the longest this vault holds;
#: title and headings are at the caps the search package clips them to.
_LONG_STEM = "2026-09-23-typesafe-search-envelope-budget-ceiling-topic-research"[:73]
_LONG_FEATURE = "typesafe-search-envelope-budget-ceiling"
_DEEP_SECTION = " > ".join(["H" * SECTION_CHARS] * 3)

#: Prose that JSON must escape now and then, as vault text does.
_PROSE = 'The "discovery" budget caps `find` at C:\\vault\\adr; see the ADR. '


def _worst_case_hit(index: int) -> SearchHit:
    def block(cap: int) -> Excerpt:
        # One unbroken line, so the clip keeps the full cap.
        text = (_PROSE * (cap // len(_PROSE) + 2))[: cap + 200]
        return Excerpt(_DEEP_SECTION, 120, 160, text)

    return _hit(
        index,
        excerpt=block(EXCERPT_CHARS),
        supporting=block(SUPPORTING_CHARS),
        stem=_LONG_STEM[:-2],
        title="T" * TITLE_CHARS,
        feature=_LONG_FEATURE,
    )


async def _reply_tokens(limit: int) -> float:
    ranking = [_worst_case_hit(i + 10) for i in range(MAX_RESULTS)]
    reply = await _reply(_ranked(ranking, limit=limit))

    payload = reply.structured_content
    assert payload is not None
    assert len(payload["hits"]) == limit
    for hit in payload["hits"]:
        assert len(hit["excerpt"]["text"]) == EXCERPT_CHARS
        assert len(hit["supporting"]["text"]) == SUPPORTING_CHARS
    wire = reply.model_dump_json(by_alias=True, exclude_none=True).encode("utf-8")
    return len(wire) / _BYTES_PER_TOKEN


@pytest.mark.unit
async def test_a_default_worst_case_reply_fits_the_discovery_budget() -> None:
    tokens = await _reply_tokens(DEFAULT_RESULTS)

    assert tokens <= _DISCOVERY_BUDGET, (
        f"{DEFAULT_RESULTS} worst-case hits cost {tokens:,.0f} tokens"
    )


@pytest.mark.unit
async def test_a_full_worst_case_reply_fits_the_reply_ceiling() -> None:
    tokens = await _reply_tokens(MAX_RESULTS)

    assert tokens <= _REPLY_CEILING, (
        f"{MAX_RESULTS} worst-case hits cost {tokens:,.0f} tokens"
    )
