"""Crossref-domain MCP tool: ``crossref``, the decisions an ADR should link.

A thin wrapper over :mod:`vaultspec_core.crossref`, the same backend the
``vault adr crossref`` CLI verb calls, so both surfaces judge the same
candidates and write the same links. No selection, bound, judgment, verdict or
next-step logic is authored here: the result is the crossref package's one
projection of the outcome, declared as a model so the tool publishes its
output schema.

The tool is registered whether or not a key is present: the tool list is a
function of core's version alone. With a key configured it sends ADR text to
the TypeSafe API, which is why it is annotated open-world. On the normal
surface it can sweep several ADRs and write link verdicts with ``apply``; on
the read-only surface it judges one ADR at a time and writes nothing.
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
from ...crossref import (
    DEFAULT_SOURCES,
    MAX_SOURCES,
    CorpusTooLargeError,
    CrossrefStatus,
    InvalidSourceError,
    crossref_adr,
    crossref_sweep,
    outcome_fields,
    sweep_fields,
)
from ..envelope import LeanResult, compact_result
from ..filters import FeatureFilter
from ..isolation import isolated_context as _isolated_context

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

logger = logging.getLogger(__name__)

__all__ = ["CrossrefResult", "register_crossref_tools"]

_CrossrefContext = Context[None, Any]

_Refs = Annotated[
    list[str],
    Field(
        default_factory=list,
        max_length=MAX_SOURCES,
        description="ADRs to judge: stem, filename, path or [[wiki-link]].",
    ),
]
_MaxSources = Annotated[int, Field(ge=1, le=MAX_SOURCES)]
_Feature = Annotated[FeatureFilter, Field(description="Sweep this feature's ADRs.")]
_Ref = Annotated[str, Field(min_length=1, description="The ADR to judge.")]


class VerdictRow(LeanResult):
    """One judged candidate: ``link`` (should be linked) or ``weak``.

    Attributes:
        stem: The candidate ADR.
        kind: ``link``, or ``weak``: declared but judged below the threshold,
            never removed automatically.
        score: The pair score.
        relation: Advisory relation of the source to the candidate.
        status: The candidate's ADR status.
        declared: Whether the source already links it.
        applied: Whether this call wrote the link.
    """

    stem: str
    kind: str
    score: float
    relation: str
    status: str | None = None
    declared: bool
    applied: bool | None = None


class SourceRow(LeanResult):
    """One source ADR's outcome.

    Attributes:
        source: The source ADR.
        status: ``ok``, ``not_configured`` or ``unavailable``.
        verdicts: Link verdicts best first, then weak ones.
        verdicts_total: Verdicts before the reply cut.
        truncated: Whether the reply cut this source's verdicts.
        links: Link verdicts.
        written: Links written.
        unjudged_declared: Declared links beyond the judged ceiling.
        write_failed: Link verdicts ``apply`` could not write.
        reason: Why a configured run failed.
        next_step: What to run instead when the source was not judged.
        remediation: The reason and the next step, as one sentence.
    """

    source: str
    status: str
    verdicts: list[VerdictRow] = Field(default_factory=list)
    verdicts_total: int = 0
    truncated: bool = False
    links: int = 0
    written: int = 0
    unjudged_declared: int | None = None
    write_failed: list[str] | None = None
    reason: str | None = None
    next_step: dict[str, Any] | None = None
    remediation: str | None = None


class CrossrefResult(LeanResult):
    """The result of a ``crossref`` call.

    Attributes:
        sources: One outcome per source judged, in order.
        judged: Sources judged.
        links: Link verdicts across sources.
        written: Links written across sources.
        remaining: Sources not reached; resume with ``after=next_after``.
        next_after: The last source processed, when sources remain.
        stopped: Why a sweep stopped early.
        usage: Requests and input tokens spent.
    """

    sources: list[SourceRow] = Field(default_factory=list)
    judged: int = 0
    links: int = 0
    written: int = 0
    remaining: int = 0
    next_after: str | None = None
    stopped: str | None = None
    usage: dict[str, int] | None = None


def _summary(payload: object) -> str:
    if not isinstance(payload, CrossrefResult):
        return type(payload).__name__
    if len(payload.sources) == 1 and payload.sources[0].status != CrossrefStatus.OK:
        first = payload.sources[0]
        return first.status.replace("_", " ") + (
            f": {first.reason}" if first.reason else ""
        )
    text = f"{payload.judged} judged, {payload.links} links"
    if payload.written:
        text += f", {payload.written} written"
    if payload.remaining:
        text += f", {payload.remaining} remaining"
    if payload.stopped:
        text += f", stopped: {payload.stopped}"
    return text


async def _run(call: functools.partial[Any]) -> Any:
    try:
        # The backend blocks on network I/O for seconds; a worker thread keeps
        # the event loop serving other requests meanwhile.
        return await anyio.to_thread.run_sync(call)
    except (InvalidSourceError, CorpusTooLargeError) as exc:
        raise ToolError(str(exc)) from exc


def register_crossref_tools(
    mcp: MCPServer[None], *, include_apply: bool = True
) -> None:
    """Register the ``crossref`` tool on *mcp*.

    Args:
        mcp: The :class:`~mcp.server.mcpserver.MCPServer` instance to decorate.
        include_apply: Register the sweeping, link-writing signature. The
            read-only surface registers a one-ADR, judge-only signature.
    """
    if include_apply:

        @mcp.tool(
            name="crossref",
            annotations=ToolAnnotations(
                read_only_hint=False,
                destructive_hint=False,
                idempotent_hint=True,
                open_world_hint=True,
            ),
        )
        @compact_result(_summary)
        @_isolated_context
        async def crossref_full(
            ctx: _CrossrefContext,
            refs: _Refs,
            feature: _Feature = None,
            isolated: bool = False,
            all_adrs: bool = False,
            after: str | None = None,
            max_sources: _MaxSources = DEFAULT_SOURCES,
            apply: bool = False,
        ) -> CrossrefResult:
            """Find the ADRs a decision should cross-reference, within fixed bounds.

            Judges each ADR against the vault's other ADRs and returns
            ``link`` verdicts (should be linked) and ``weak`` ones (declared,
            judged below the threshold). One ref judges that ADR; several refs,
            ``feature``, ``isolated`` or ``all_adrs`` sweep in stem order,
            at most ``max_sources``, resumable with ``after=next_after``.
            ``apply`` writes new link verdicts into each source's
            ``related:``. Relations are advisory. Without a TypeSafe key it
            sends nothing and returns ``not_configured`` with a next step.

            Args:
                ctx: The MCP request context (unused).
                refs: ADRs to judge.
                feature: Sweep this feature's ADRs.
                isolated: Sweep only ADRs that link no other ADR.
                all_adrs: Sweep every ADR that still governs.
                after: Resume a sweep after this stem.
                max_sources: Most ADRs one sweep judges.
                apply: Write new link verdicts.
            """
            _ = ctx
            root = _get_ctx().target_dir
            logger.info(
                "crossref: refs=%d feature=%r isolated=%s all=%s apply=%s",
                len(refs),
                feature,
                isolated,
                all_adrs,
                apply,
            )
            sweeping = (
                len(refs) != 1
                or feature is not None
                or isolated
                or all_adrs
                or after is not None
            )
            if not sweeping:
                outcome = await _run(
                    functools.partial(crossref_adr, root, refs[0], apply=apply)
                )
                return CrossrefResult.model_validate(outcome_fields(outcome))
            sweep = await _run(
                functools.partial(
                    crossref_sweep,
                    root,
                    refs,
                    feature=feature,
                    isolated=isolated,
                    all_adrs=all_adrs,
                    after=after,
                    max_sources=max_sources,
                    apply=apply,
                )
            )
            return CrossrefResult.model_validate(sweep_fields(sweep))

        _ = crossref_full
        return

    @mcp.tool(
        name="crossref",
        annotations=ToolAnnotations(
            read_only_hint=True,
            idempotent_hint=True,
            open_world_hint=True,
        ),
    )
    @compact_result(_summary)
    @_isolated_context
    async def crossref_read_only(ctx: _CrossrefContext, ref: _Ref) -> CrossrefResult:
        """Find the ADRs a decision should cross-reference, within fixed bounds.

        Judges one ADR against the vault's other ADRs and returns ``link``
        verdicts (should be linked) and ``weak`` ones (declared, judged below
        the threshold). Relations are advisory. Writes nothing. Without a
        TypeSafe key it sends nothing and returns ``not_configured`` with a
        next step.

        Args:
            ctx: The MCP request context (unused).
            ref: The ADR to judge: stem, filename, path or [[wiki-link]].
        """
        _ = ctx
        root = _get_ctx().target_dir
        outcome = await _run(functools.partial(crossref_adr, root, ref))
        return CrossrefResult.model_validate(outcome_fields(outcome))

    _ = crossref_read_only
