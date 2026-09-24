"""Search-domain MCP tool: ``search``, hosted vault search with verbatim excerpts.

A thin wrapper over :func:`vaultspec_core.search.search_vault`, the same
service the ``vault search`` CLI verb calls, so both surfaces rank the same
records and quote the same passages. No ranking, credential, validation,
verdict or next-step logic is authored here: the result is the search
package's one projection of a :class:`~vaultspec_core.search.SearchOutcome`,
the same fields ``vault search --json`` carries, declared as a model so the
tool publishes its output schema.

The search package bounds every excerpt, title and section in encoded bytes
before this layer sees them, marks each excerpt it cut, and projects each hit
once for every surface; this layer carries that projection as it is. The page
carries the shared window fields, so the worst-case reply stays inside the
envelope budget whatever the vault holds and wherever the workspace lives.

The tool is registered on both surfaces and whether or not a key is present:
the tool list is a function of core's version alone. It mutates nothing
locally, but with a key configured it sends vault text to the TypeSafe API,
which is why it is annotated open-world. Without a key it returns
``not_configured`` and sends nothing.
"""

from __future__ import annotations

import functools
import logging
from typing import TYPE_CHECKING, Annotated, Any

import anyio.to_thread
from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from ...core.types import get_context as _get_ctx
from ...search import (
    DEFAULT_RESULTS,
    MAX_QUERY_CHARS,
    MAX_RESULTS,
    Excerpt,
    InvalidQueryError,
    NextStep,
    SearchStatus,
    SearchUsage,
    SearchVerdict,
    UnavailableReason,
    outcome_fields,
    outcome_label,
    search_vault,
    unscored_note,
)
from ..envelope import LeanResult, LeanShape, compact_result
from ..filters import DateFilter, FeatureFilter, SearchTypeFilter
from ..isolation import isolated_context as _isolated_context

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from ...search import SearchOutcome

logger = logging.getLogger(__name__)

__all__ = ["SearchResult", "register_search_tools", "search_result"]

#: The request context type the tool declares; the SDK resolves it at
#: registration, so the alias is bound at runtime rather than type-checking.
_SearchToolContext = Context[None, Any]

#: The query, bounded as the service bounds it so an overlong query is refused
#: by schema validation before any work starts.
_Query = Annotated[str, Field(min_length=1, max_length=MAX_QUERY_CHARS)]

#: Hits per page, within the search package's hard ceiling.
_Limit = Annotated[int, Field(ge=1, le=MAX_RESULTS)]

#: ``search``'s record-type filter: the shared declaration of the types search
#: ranks, every one of them when the caller names none.
_SearchTypes = Annotated[SearchTypeFilter, Field(description="Default: all.")]


class SearchHitRow(LeanResult):
    """One ranked record, as :func:`~vaultspec_core.search.hit_fields` projects it.

    The record's name is its path's stem, so it is not carried twice. No
    ``file://`` locator is carried either: ``path`` is relative to the
    workspace the caller already has open, and a locator built on the
    workspace root would grow the reply with that root's length.

    Attributes:
        path: The record's path relative to the workspace root.
        type: The record type.
        feature: The record's feature tag, without ``#``.
        date: The record's frontmatter date.
        title: The record's H1 text.
        score: The ranking score the hits are ordered by.
        answers: Probability that the record states the answer.
        premise_conflict: Probability that the record contradicts an
            assumption in the query; reported, never folded into ``score``.
        blob_hash: Git blob id of the file the line ranges refer to.
        excerpt: The block judged to answer; absent when none was chosen.
        supporting: A second block, when the answer spans two.
    """

    path: str
    type: str
    feature: str
    date: str
    title: str
    score: float
    answers: float
    premise_conflict: float
    blob_hash: str
    excerpt: Annotated[Excerpt, LeanShape()] | None = None
    supporting: Annotated[Excerpt, LeanShape()] | None = None


class SearchResult(LeanResult):
    """The whole-call result of a ``search`` invocation.

    The query is not echoed: the caller sent it, and an echo of up to the
    query ceiling would spend the reply budget on text the caller already has.

    Attributes:
        status: ``ok``, ``not_configured`` or ``unavailable``.
        answered: Whether any record was judged to answer the query.
        verdict: What a ranked page says about the vault (``ok`` only).
        hits: The ranked page, best first.
        returned: Hits on this page (``ok`` only).
        total: Hits the ranking held before the page cap (``ok`` only).
        truncated: Whether the ranking held more than this page (``ok``
            only); raising ``limit`` reaches them.
        reason: Why a configured search failed (``unavailable`` only).
        next_step: The search to run instead when no ranking was produced.
        remediation: The reason and the next step, as one sentence.
        usage: Cost and diagnostics; absent when nothing was sent.
    """

    status: str
    answered: bool
    verdict: str | None = None
    hits: list[SearchHitRow] = Field(default_factory=list)
    returned: int | None = None
    total: int | None = None
    truncated: bool | None = None
    reason: str | None = None
    next_step: Annotated[NextStep, LeanShape()] | None = None
    remediation: str | None = None
    usage: Annotated[SearchUsage, LeanShape()] | None = None


def search_result(outcome: SearchOutcome) -> SearchResult:
    """Project a search outcome onto the ``search`` tool's result.

    Args:
        outcome: The outcome :func:`~vaultspec_core.search.search_vault`
            returned.

    Returns:
        The tool result, validated from
        :func:`~vaultspec_core.search.outcome_fields`.
    """
    return SearchResult.model_validate(outcome_fields(outcome))


def _search_summary(payload: object) -> str:
    """Summarise a search result in one line.

    Args:
        payload: The :class:`SearchResult` the tool returned.

    Returns:
        The hit count before the search package's outcome label and unscored
        note: ``"3 hits, answered"`` or ``"unavailable (rate_limited)"``, for
        example.
    """
    if not isinstance(payload, SearchResult):
        return type(payload).__name__
    status = SearchStatus(payload.status)
    label = outcome_label(
        status,
        None if payload.verdict is None else SearchVerdict(payload.verdict),
        None if payload.reason is None else UnavailableReason(payload.reason),
    )
    if status is not SearchStatus.OK:
        return label
    count = len(payload.hits)
    shown = f"{count} of {payload.total}" if payload.truncated else str(count)
    summary = f"{shown} hit{'' if count == 1 else 's'}, {label}"
    unscored = unscored_note(0 if payload.usage is None else payload.usage.unscored)
    return summary if unscored is None else f"{summary}, {unscored}"


def register_search_tools(mcp: MCPServer[None]) -> None:
    """Register the ``search`` tool on *mcp*.

    ``search`` is read-only and idempotent, and open-world: with a key
    configured it sends vault text to an external API. It is registered on
    the read-only surface too, since it mutates nothing.

    Args:
        mcp: The :class:`~mcp.server.mcpserver.MCPServer` instance to decorate.
    """

    @mcp.tool(
        annotations=ToolAnnotations(
            read_only_hint=True,
            idempotent_hint=True,
            open_world_hint=True,
        ),
    )
    @compact_result(_search_summary)
    @_isolated_context
    async def search(
        ctx: _SearchToolContext,
        query: _Query,
        type: _SearchTypes = None,
        feature: FeatureFilter = None,
        date: DateFilter = None,
        limit: _Limit = DEFAULT_RESULTS,
    ) -> SearchResult:
        """Answer a question from the vault, quoting the passage that answers.

        Ranks records against a natural-language ``query``, best first. Each
        hit quotes its answering block verbatim with its file lines and
        ``blob_hash``; ``truncated`` marks a block cut at ``line_end``.
        ``verdict`` says whether the records read answer; ``premise_conflict``
        is the probability a record contradicts the question. When search
        declines (``not_configured``: no TypeSafe key, nothing sent) or fails
        (``unavailable``), run ``next_step.command`` instead. With a key set,
        vault text is sent to the TypeSafe API.

        Args:
            ctx: The MCP request context (unused).
            query: The question, in plain language.
            limit: Hits to return.
        """
        _ = ctx
        root_dir = _get_ctx().target_dir
        logger.info(
            "search: %d chars type=%r feature=%r date=%r limit=%s",
            len(query),
            type,
            feature,
            date,
            limit,
        )
        run = functools.partial(
            search_vault,
            root_dir,
            query,
            doc_types=type,
            feature=feature,
            date=date,
            limit=limit,
        )
        try:
            # The service blocks on network I/O for about a second; a worker
            # thread keeps the event loop serving other requests meanwhile.
            outcome = await anyio.to_thread.run_sync(run)
        except InvalidQueryError as exc:
            raise ToolError(str(exc)) from exc
        logger.debug("search: %s, %d hit(s)", outcome.status, len(outcome.hits))
        return search_result(outcome)

    _ = search  # bound by the decorator; silence unused warnings
