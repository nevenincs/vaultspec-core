"""The typed results of hosted vault search.

A search has three honest outcomes, and the type carries which one happened
rather than leaving a caller to infer it from an empty list:

``ok``
    The vault was judged. ``hits`` may be empty, and ``answered`` says whether
    any record was judged to answer the query - an empty page and "nothing in
    the vault answers this" are the same fact, stated once.
``not_configured``
    No hosted-search credential is available. Nothing was sent anywhere; the
    caller routes to the agent-level fallback.
``unavailable``
    Hosted search was configured but failed. ``reason`` names the failure
    class, and no partial ranking is returned: mixing judged and unjudged
    records would present a guess as a result.

Every excerpt is the record's own text at a reported line range, never text a
model wrote, so a caller can quote it or open the file at that span. The
``blob_hash`` pins the file version the line range belongs to.

The bounded-window vocabulary is :class:`~vaultspec_core.core.windowing.Window`,
shared with every other capped surface, not a search-specific restatement.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from ..core.windowing import Window
    from ..vaultcore.models import DocType

__all__ = [
    "DEFAULT_RESULTS",
    "MAX_RESULTS",
    "CredentialSource",
    "Excerpt",
    "HostedSearchConfig",
    "SearchHit",
    "SearchOutcome",
    "SearchStatus",
    "SearchUsage",
    "UnavailableReason",
]

#: Hits returned when a caller names no limit: five hits with their excerpts
#: sit well inside the discovery reply budget.
DEFAULT_RESULTS: Final = 5

#: The most hits one search returns. Every shortlisted record is judged
#: regardless, so a larger page would only repeat weaker candidates.
MAX_RESULTS: Final = 20


class SearchStatus(StrEnum):
    """Which of the three outcomes a search produced."""

    OK = "ok"
    NOT_CONFIGURED = "not_configured"
    UNAVAILABLE = "unavailable"


class UnavailableReason(StrEnum):
    """Why a configured hosted search produced no result.

    A content rejection is deliberately absent: it affects one record, which
    is reported as unscored in :class:`SearchUsage`, and never fails a search.
    """

    CREDENTIAL_REJECTED = "credential_rejected"
    RATE_LIMITED = "rate_limited"
    TRANSPORT = "transport"
    DEADLINE = "deadline"
    INVALID_RESPONSE = "invalid_response"
    REQUEST_TOO_LARGE = "request_too_large"


class CredentialSource(StrEnum):
    """Where the hosted-search credential was found."""

    ENVIRONMENT = "environment"
    DOTENV = "dotenv"


@dataclass(frozen=True)
class HostedSearchConfig:
    """Whether hosted search is configured, and from where. Never the key."""

    configured: bool
    source: CredentialSource | None = None


@dataclass(frozen=True)
class Excerpt:
    """A verbatim span of a record.

    Attributes:
        section: The heading path the span sits under, outermost first,
            joined with ``" > "``; empty before the first heading.
        line_start: First line of the span in the file, 1-based.
        line_end: Last line of the span, inclusive.
        text: The span exactly as it appears in the file.
    """

    section: str
    line_start: int
    line_end: int
    text: str


@dataclass(frozen=True)
class SearchHit:
    """One ranked record.

    Attributes:
        name: The record's file stem.
        path: The record's path relative to the workspace root, POSIX form.
        doc_type: The record's type.
        feature: The record's feature tag, without ``#``.
        date: The record's frontmatter date.
        title: The record's H1 text.
        score: The composite ranking score the hits are ordered by.
        answers: Probability that the record states the answer.
        premise_conflict: Probability that the record contradicts a factual
            assumption in the query; reported, never folded into ``score``.
        excerpt: The block judged to answer, or ``None`` when the record was
            ranked but no block was chosen.
        supporting: A second block, when the answer spans two.
        blob_hash: Git blob id of the file the line ranges refer to.
    """

    name: str
    path: str
    doc_type: DocType
    feature: str
    date: str
    title: str
    score: float
    answers: float
    premise_conflict: float
    excerpt: Excerpt | None
    supporting: Excerpt | None
    blob_hash: str


@dataclass(frozen=True)
class SearchUsage:
    """What a search cost, for diagnostics.

    Attributes:
        model: The model version that answered.
        requests: Provider requests made.
        input_tokens: Input tokens billed across those requests.
        elapsed_ms: Wall time of the hosted stages.
        unscored: Records the provider's content filter refused to read.
    """

    model: str
    requests: int
    input_tokens: int
    elapsed_ms: float
    unscored: int


@dataclass(frozen=True)
class SearchOutcome:
    """The result of one search.

    Attributes:
        status: Which outcome occurred.
        query: The query as submitted.
        answered: Whether any record was judged to answer the query.
        hits: The ranked page, best first. Empty unless ``status`` is ``ok``.
        window: The bound applied to ``hits``; ``None`` unless ``ok``.
        reason: Why hosted search failed; set only when ``unavailable``.
        usage: Cost and diagnostics; ``None`` when nothing was sent.
    """

    status: SearchStatus
    query: str
    answered: bool = False
    hits: tuple[SearchHit, ...] = ()
    window: Window | None = None
    reason: UnavailableReason | None = None
    usage: SearchUsage | None = None
