"""The one projection of a cross-reference outcome that every surface carries.

The MCP ``crossref`` tool and ``vault adr crossref --json`` return the same
fields at the same precision, built here rather than chosen by each surface.

One shape serves both: a single source is projected as a sweep of one.
Replies are bounded. A source lists only its ``link`` and ``weak`` verdicts
beside its counts, and a reply lists at most :data:`REPLY_VERDICTS` verdict
rows across all its sources; a source whose rows were cut says so with
``truncated`` and keeps its ``verdicts_total``, so a caller always sees what it
did not receive. Cost is summed once, for the whole reply.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from ..search._models import NextStepKind
from ..search._wire import SCORE_PLACES
from ._models import CrossrefStatus

if TYPE_CHECKING:
    from ..search._models import NextStep
    from ._models import CrossrefOutcome, SweepOutcome, Verdict

__all__ = ["REPLY_VERDICTS", "outcome_fields", "remediation", "sweep_fields"]

#: Verdict rows one sweep reply carries across all its sources. A row with a
#: bounded title is under 100 tokens, so the reply stays under the envelope's
#: hard ceiling however many sources the sweep judged.
REPLY_VERDICTS: Final = 80

_UNAVAILABLE: Final[dict[str, str]] = {
    "credential_rejected": (
        "The TypeSafe API rejected the hosted-search key; check or rotate it"
    ),
    "content_rejected": "The TypeSafe API refused to read this ADR",
    "rate_limited": "The TypeSafe API is rate limiting this key; retry shortly",
    "transport": "The TypeSafe API could not be reached; retry",
    "deadline": "Cross-referencing ran out of time; retry",
    "invalid_response": (
        "The TypeSafe API returned a response that could not be used; retry"
    ),
    "request_too_large": "This ADR exceeded the provider's request size",
}


def remediation(outcome: CrossrefOutcome) -> str | None:
    """Say why a source was not judged and what to do instead.

    Args:
        outcome: One source's outcome.

    Returns:
        One sentence for ``not_configured`` and ``unavailable``; ``None`` for
        ``ok``.
    """
    step = outcome.next_step
    if step is None:
        return None
    if outcome.status is CrossrefStatus.NOT_CONFIGURED:
        from ..search._credential import CREDENTIAL_VARIABLE

        cause = (
            "ADR cross-referencing needs hosted search: set "
            f"{CREDENTIAL_VARIABLE} to enable it"
        )
    else:
        reason = outcome.reason.value if outcome.reason else "transport"
        cause = _UNAVAILABLE.get(reason, _UNAVAILABLE["transport"])
    return f"{cause}, {_fallback(step)}"


def _fallback(step: NextStep) -> str:
    if step.kind is NextStepKind.RAG_SEARCH:
        return f"or find related decisions with `{step.command}`."
    return (
        f"or list the ADRs with `{step.command}` (MCP: `find`) and read the "
        "candidates that share its subject."
    )


def _verdict_fields(verdict: Verdict) -> dict[str, object]:
    """One verdict row. The stem names the ADR; its title stays in the file."""
    fields: dict[str, object] = {
        "stem": verdict.stem,
        "kind": verdict.kind.value,
        "score": round(verdict.score, SCORE_PLACES),
        "relation": verdict.relation,
        "declared": verdict.declared,
    }
    if verdict.status is not None:
        fields["status"] = verdict.status.value
    if verdict.applied:
        fields["applied"] = True
    return fields


def _decline_fields(outcome: CrossrefOutcome, fields: dict[str, object]) -> None:
    if outcome.reason is not None:
        fields["reason"] = outcome.reason.value
    if outcome.next_step is not None:
        step = outcome.next_step
        fields["next_step"] = {
            "kind": step.kind.value,
            "types": [doc_type.value for doc_type in step.types],
            "command": step.command,
        }
        fields["remediation"] = remediation(outcome)


def _sweep_source(outcome: CrossrefOutcome, budget: int) -> dict[str, object]:
    """One source of a sweep, compact: its rows within *budget*, then counts."""
    rows = outcome.verdicts[: max(budget, 0)]
    fields: dict[str, object] = {
        "source": outcome.source,
        "status": outcome.status.value,
        "verdicts": [_verdict_fields(verdict) for verdict in rows],
        "verdicts_total": len(outcome.verdicts),
        "truncated": len(rows) < len(outcome.verdicts),
        "links": len(outcome.links),
        "written": len(outcome.written),
    }
    if outcome.write_failed:
        fields["write_failed"] = list(outcome.write_failed)
    if outcome.bounds is not None and outcome.bounds.unjudged_declared:
        fields["unjudged_declared"] = len(outcome.bounds.unjudged_declared)
    _decline_fields(outcome, fields)
    return fields


def outcome_fields(outcome: CrossrefOutcome) -> dict[str, object]:
    """Project one source's outcome: the sweep projection of a sweep of one.

    Every surface carries one shape, so a caller reads a single-source reply
    and a sweep reply the same way.

    Args:
        outcome: The outcome.

    Returns:
        The JSON-ready fields.
    """
    from ._models import SweepOutcome

    return sweep_fields(SweepOutcome(outcomes=(outcome,)))


def sweep_fields(sweep: SweepOutcome) -> dict[str, object]:
    """Project a sweep onto the fields a reply carries, within the row budget.

    Each source is compact - its verdict rows and counts - and the sweep's
    cost is summed once, so the reply stays under the envelope ceiling at the
    most sources and verdicts a sweep can hold.

    Args:
        sweep: The sweep outcome.

    Returns:
        The JSON-ready fields: each source's projection in order, the totals,
        the sources not reached, the resume cursor and why the sweep stopped.
    """
    budget = REPLY_VERDICTS
    sources: list[dict[str, object]] = []
    for outcome in sweep.outcomes:
        sources.append(_sweep_source(outcome, budget))
        budget -= min(len(outcome.verdicts), max(budget, 0))
    usages = [o.usage for o in sweep.outcomes if o.usage is not None]
    fields: dict[str, object] = {
        "sources": sources,
        "judged": sum(1 for o in sweep.outcomes if o.status is CrossrefStatus.OK),
        "links": sum(len(o.links) for o in sweep.outcomes),
        "written": sum(len(o.written) for o in sweep.outcomes),
        "remaining": sweep.remaining,
    }
    if sweep.next_after is not None:
        fields["next_after"] = sweep.next_after
    if sweep.stopped is not None:
        fields["stopped"] = sweep.stopped
    if usages:
        fields["usage"] = {
            "requests": sum(u.requests for u in usages),
            "input_tokens": sum(u.input_tokens for u in usages),
            "unscored": sum(u.unscored for u in usages),
        }
    return fields
