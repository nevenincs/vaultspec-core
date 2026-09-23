"""The typed results of hosted vault search.

A search has three honest outcomes, and the type carries which one happened
rather than leaving a caller to infer it from an empty list:

``ok``
    The vault was judged. ``answered`` says whether any record was judged to
    answer the query. A record the provider would not read in full is counted
    in ``usage.unscored`` rather than failing the search, so "nothing answers"
    is a verdict on the whole vault only when nothing went unscored; see
    :attr:`SearchOutcome.abstained`. ``hits`` may be empty only when every
    record was read: a search whose refusals leave nothing ranked is
    ``unavailable`` instead.
``not_configured``
    No hosted-search credential is available. Nothing was sent anywhere.
``unavailable``
    Hosted search was configured but failed. ``reason`` names the failure
    class, and no partial ranking is returned: mixing judged and unjudged
    records would present a guess as a result.

Both outcomes that did not rank carry a :class:`NextStep`: the search the
caller should run instead, resolved from what this workspace provides. Core
names that search; it never runs it.

Every excerpt is the record's own text at a reported line range, never text a
model wrote, so a caller can quote it or open the file at that span. The
``blob_hash`` pins the file version the line range belongs to. Excerpts,
titles and sections are bounded once, in encoded bytes, before any surface
sees them, so every surface carries the same text and a reply's size does not
depend on the script the vault is written in.

The bounded-window vocabulary is :class:`~vaultspec_core.core.windowing.Window`,
shared with every other capped surface, not a search-specific restatement.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Final

from ..vaultcore.models import DocType
from ._questions import PREMISE_CONFLICT_THRESHOLD, SHORTLIST_LEXICAL, SHORTLIST_SIZE

if TYPE_CHECKING:
    from ..core.windowing import Window

__all__ = [
    "DEFAULT_RESULTS",
    "EXCERPT_BYTES",
    "MAX_QUERY_CHARS",
    "MAX_RESULTS",
    "SUPPORTING_BYTES",
    "CredentialSource",
    "Excerpt",
    "HostedSearchConfig",
    "InvalidQueryError",
    "NextStep",
    "NextStepKind",
    "SearchHit",
    "SearchOutcome",
    "SearchStatus",
    "SearchUsage",
    "SearchVerdict",
    "UnavailableReason",
    "UnsearchableTypeError",
]

#: Hits returned when a caller names no limit. Four hits with their excerpts
#: at the caps below stay inside the discovery reply budget with room for
#: long titles and headings; raising the limit reaches the rest.
DEFAULT_RESULTS: Final = 4

#: The most hits one search returns: every record a search reads in full, so
#: raising the limit reaches the whole ranking and no page needs an offset.
#: Eleven hits with capped excerpts stay under the envelope's hard reply
#: ceiling.
MAX_RESULTS: Final = SHORTLIST_SIZE + SHORTLIST_LEXICAL

#: UTF-8 bytes of a hit's answering excerpt, kept as whole lines with
#: ``core.windowing.clip_lines``. Records are cut into blocks of at most this
#: many bytes, so the block the provider picks is the text returned whole:
#: clipping longer blocks from the top dropped the answer when it closed the
#: block. Only a single line longer than the cap is still clipped. Bytes, not
#: characters, because the reply budget is measured in bytes: a character cap
#: let a CJK or emoji excerpt cost three or four times its ASCII size.
#: Sized with :data:`SUPPORTING_BYTES` against the costliest page: CJK text
#: one character per line, whose newlines JSON doubles, under five-level
#: heading paths at every cap. Eleven such hits measured 34,163 reply bytes
#: (9,874 tokens, under the 10,000 ceiling) and four measured 12,627 (3,649,
#: under the 4,000 discovery budget); 900 and 400 bytes reached about 11,000.
EXCERPT_BYTES: Final = 700

#: UTF-8 bytes of a hit's supporting excerpt.
SUPPORTING_BYTES: Final = 300


#: The longest query accepted. A query is a question, not a document: every
#: request carries it, so an unbounded query would crowd out the records it is
#: judged against.
MAX_QUERY_CHARS: Final = 2_000


class InvalidQueryError(ValueError):
    """The search request is invalid, before anything is read or sent.

    The query is blank or longer than :data:`MAX_QUERY_CHARS`, or a filter
    names what search cannot rank. Its own type, so a surface reports exactly
    this as invalid input and lets any other failure surface as the defect it
    is.
    """


class UnsearchableTypeError(InvalidQueryError):
    """A record-type filter names a type search does not rank.

    Refused rather than applied: the filter would drop every record of that
    type and come back as a page that reads as "nothing answers".
    """


class SearchStatus(StrEnum):
    """Which of the three outcomes a search produced."""

    OK = "ok"
    NOT_CONFIGURED = "not_configured"
    UNAVAILABLE = "unavailable"


class SearchVerdict(StrEnum):
    """What a ranked page says about the vault.

    The verdict is only as wide as what was read: "nothing answers" is a
    statement about the whole vault, so it needs every record read.
    """

    ANSWERED = "answered"
    NOTHING_ANSWERS = "nothing_answers"
    NONE_READ_ANSWERS = "none_read_answers"

    @property
    def sentence(self) -> str:
        """The verdict as every surface words it."""
        return _VERDICT_SENTENCES[self]


_VERDICT_SENTENCES: Final[dict[SearchVerdict, str]] = {
    SearchVerdict.ANSWERED: "answered",
    SearchVerdict.NOTHING_ANSWERS: "nothing in the vault answers this",
    SearchVerdict.NONE_READ_ANSWERS: "no record that was read answers this",
}


class NextStepKind(StrEnum):
    """Which search to run when hosted search did not rank.

    Members:
        RAG_SEARCH: A vaultspec-rag vault search. Chosen when the workspace
            provisions the rag companion; provisioning is configuration, not
            liveness, so the rag search can itself be unavailable.
        LISTING: Core's listing verbs, with grep over the listed records for
            the passage. Always available, and the one route when rag is not
            provisioned.
    """

    RAG_SEARCH = "rag_search"
    LISTING = "listing"


@dataclass(frozen=True)
class NextStep:
    """The search a caller runs when hosted search did not rank.

    Attributes:
        kind: Which search it is.
        types: The record types it covers: the ones the request named, or
            every searchable type. Held as record types in name order, however
            they were given, so the step reads the same on every surface.
        command: The command line that runs it, with ``<intent>`` standing
            for the caller's question.
    """

    kind: NextStepKind
    types: tuple[DocType, ...]
    command: str

    def __post_init__(self) -> None:
        """Hold ``types`` as record types in name order."""
        object.__setattr__(
            self, "types", tuple(sorted(DocType(name) for name in self.types))
        )


class UnavailableReason(StrEnum):
    """Why a configured hosted search produced no result.

    A content rejection normally affects one record, which is reported as
    unscored in :class:`SearchUsage` while the rest are ranked.
    ``CONTENT_REJECTED`` is the case where that leaves nothing to rank: the
    provider refused the query itself, or every record the ranking needed.
    """

    CREDENTIAL_REJECTED = "credential_rejected"
    CONTENT_REJECTED = "content_rejected"
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

    ``text`` is exactly the file's lines ``line_start`` through ``line_end``.
    A block longer than its byte cap keeps its leading whole lines, with
    ``line_end`` the last line kept and ``truncated`` set; the block goes on
    at ``line_end + 1``. The one exception is a block whose first line alone
    exceeds the cap: ``text`` is then the leading part of that line, cut at a
    whole character, and ``line_end`` equals ``line_start``.

    Attributes:
        section: The heading path the span sits under, outermost first,
            joined with ``" > "``; empty before the first heading. Each
            heading is bounded in bytes.
        line_start: First line of the span in the file, 1-based.
        line_end: Last line of the span, inclusive.
        text: The span exactly as it appears in the file.
        truncated: Whether the block the model chose continues past ``text``.
    """

    section: str
    line_start: int
    line_end: int
    text: str
    truncated: bool = False


@dataclass(frozen=True)
class SearchHit:
    """One ranked record.

    Attributes:
        name: The record's file stem.
        path: The record's path relative to the workspace root, POSIX form.
        doc_type: The record's type.
        feature: The record's feature tag, without ``#``.
        date: The record's frontmatter date.
        title: The record's H1 text, bounded in bytes.
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

    @property
    def contradicts_premise(self) -> bool:
        """Whether the record likely contradicts an assumption in the query.

        Advisory: the threshold separated the false-premise queries it was
        measured on, but not by a wide margin.
        """
        return self.premise_conflict >= PREMISE_CONFLICT_THRESHOLD


@dataclass(frozen=True)
class SearchUsage:
    """What a search cost, for diagnostics.

    Attributes:
        model: The model version that answered.
        requests: Provider requests made.
        input_tokens: Input tokens billed across those requests.
        elapsed_ms: Wall time of the hosted stages, in whole milliseconds.
        unscored: Records the provider would not read in full: its content
            filter refused them, or one of their windows exceeded the request
            bound. A record refused only in part is still ranked, on the text
            that was read, and is counted here too.
    """

    model: str
    requests: int
    input_tokens: int
    elapsed_ms: int
    unscored: int


@dataclass(frozen=True)
class SearchOutcome:
    """The result of one search.

    Attributes:
        status: Which outcome occurred.
        query: The query as submitted.
        answered: Whether any record was judged to answer the query. ``False``
            is a verdict on the records that were read; it covers the whole
            vault only when :attr:`abstained` holds.
        hits: The ranked page, best first. Empty unless ``status`` is ``ok``.
        window: The bound applied to ``hits``; ``None`` unless ``ok``.
        reason: Why hosted search failed; set only when ``unavailable``.
        usage: Cost and diagnostics; ``None`` when nothing was sent.
        next_step: The search to run instead; set exactly when the outcome
            is not ``ok``.

    Raises:
        ValueError: If ``next_step`` is missing from an outcome that did not
            rank, or present on one that did.
    """

    status: SearchStatus
    query: str
    answered: bool = False
    hits: tuple[SearchHit, ...] = ()
    window: Window | None = None
    reason: UnavailableReason | None = None
    usage: SearchUsage | None = None
    next_step: NextStep | None = None

    def __post_init__(self) -> None:
        """Hold the one invariant every surface relies on: a decline names a step."""
        ranked = self.status is SearchStatus.OK
        if ranked == (self.next_step is not None):
            msg = (
                "a ranked outcome carries no next step"
                if ranked
                else f"a {self.status.value} outcome must name its next step"
            )
            raise ValueError(msg)

    @property
    def unscored(self) -> int:
        """Records the provider would not read in full; ``0`` if none was sent."""
        return 0 if self.usage is None else self.usage.unscored

    @property
    def abstained(self) -> bool:
        """Whether the search read every record and judged that none answers.

        This, not ``not answered``, is what a surface may report as "nothing
        in the vault answers this": with a record unscored, the record that
        answers may be the one that was not read.
        """
        return (
            self.status is SearchStatus.OK and not self.answered and not self.unscored
        )

    @property
    def verdict(self) -> SearchVerdict | None:
        """What the ranked page says about the vault; ``None`` unless ``ok``."""
        if self.status is not SearchStatus.OK:
            return None
        if self.answered:
            return SearchVerdict.ANSWERED
        if self.abstained:
            return SearchVerdict.NOTHING_ANSWERS
        return SearchVerdict.NONE_READ_ANSWERS
