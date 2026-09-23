"""The typed results of cross-referencing an ADR.

Cross-referencing a source ADR has the same three honest outcomes hosted search
has, and the type carries which one happened:

``ok``
    The source was judged. Its verdicts list the candidates judged to be links
    and the declared links judged weak; every other candidate is counted, not
    listed. A pair the provider refused to read is counted in
    ``usage.unscored`` rather than failing the source.
``not_configured``
    No hosted-search credential is available. Nothing was sent anywhere.
``unavailable``
    The credential is configured but the provider failed. ``reason`` names the
    failure class; no partial verdicts are returned for that source.

Both outcomes that did not judge carry the next step: the search to run
instead, resolved exactly as hosted search resolves it, over ADRs.

A sweep judges several sources one after another under one run deadline. Its
outcome lists each source's outcome in order, the sources it did not reach,
and the stem to resume after.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.enums import AdrStatus
    from ..search._models import NextStep, UnavailableReason

__all__ = [
    "Bounds",
    "CorpusTooLargeError",
    "CrossrefOutcome",
    "CrossrefStatus",
    "CrossrefUsage",
    "InvalidSourceError",
    "SweepOutcome",
    "Verdict",
    "VerdictKind",
]


class CorpusTooLargeError(ValueError):
    """The ADR directory holds more records than one run may read.

    Attributes:
        count: The number of ADR files found.
    """

    def __init__(self, count: int) -> None:
        from ._questions import MAX_CORPUS

        super().__init__(
            f"the vault holds {count} ADRs; cross-referencing reads at most "
            f"{MAX_CORPUS}"
        )
        self.count = count


class InvalidSourceError(ValueError):
    """The request names no ADR, or an ADR this vault does not hold.

    Refused before anything is read in full or sent.
    """


class CrossrefStatus(StrEnum):
    """Which outcome judging one source produced."""

    OK = "ok"
    NOT_CONFIGURED = "not_configured"
    UNAVAILABLE = "unavailable"


class VerdictKind(StrEnum):
    """What a judged pair means for the source's ``related:`` field.

    Members:
        LINK: Judged a cross-reference; the source should link it. Applying
            writes it when it is not declared already.
        WEAK: A link the source declares, judged below the threshold. Never
            removed automatically; listed for a curator to read.
    """

    LINK = "link"
    WEAK = "weak"


@dataclass(frozen=True)
class Verdict:
    """One judged candidate worth reporting.

    Attributes:
        stem: The candidate ADR's stem.
        title: The candidate's title, bounded.
        feature: The candidate's feature tag, without ``#``.
        status: The candidate's declared ADR status, or ``None``.
        kind: The verdict.
        score: The pair score: the mean of the need and artifact judgments and
            one minus the useless-link judgment.
        relation: The most probable relation of the source to the candidate.
            Advisory: it tells an author which pairs to read in full, never
            which way to decide.
        declared: Whether the source already links the candidate.
        applied: Whether this run wrote the link.
    """

    stem: str
    title: str
    feature: str
    status: AdrStatus | None
    kind: VerdictKind
    score: float
    relation: str
    declared: bool
    applied: bool = False


@dataclass(frozen=True)
class Bounds:
    """The ceilings one source was judged under, reported with its outcome.

    Attributes:
        corpus: ADRs read by the code stage.
        pool: Candidates passed to the Choice stage.
        judged: Candidates judged pairwise.
        unjudged_declared: Declared links neither in the cut nor among the
            extra declared links judged.
    """

    corpus: int
    pool: int
    judged: int
    unjudged_declared: tuple[str, ...] = ()


@dataclass(frozen=True)
class CrossrefUsage:
    """What judging one source cost.

    Attributes:
        model: The model version the provider reported, or the pinned one.
        requests: Evaluations sent, each at most the transport's attempts.
        input_tokens: Billed input tokens.
        elapsed_ms: Wall time spent on the provider.
        unscored: Evaluations the provider's edge refused to read: Choice
            chunks, whose candidates kept their code-only rank, and pairs,
            which were left unjudged.
    """

    model: str
    requests: int
    input_tokens: int
    elapsed_ms: int
    unscored: int = 0


@dataclass(frozen=True)
class CrossrefOutcome:
    """The outcome of cross-referencing one source ADR.

    Attributes:
        source: The source ADR's stem.
        status: Which outcome it is.
        verdicts: ``link`` verdicts best first, then ``weak`` ones.
        bounds: The ceilings applied; ``None`` when nothing was judged.
        dropped: Judged candidates that are neither links nor declared.
        reason: Why a configured run failed (``unavailable`` only).
        next_step: The search to run instead (not ``ok``).
        usage: What was sent; ``None`` when nothing was.
    """

    source: str
    status: CrossrefStatus
    verdicts: tuple[Verdict, ...] = ()
    bounds: Bounds | None = None
    dropped: int = 0
    reason: UnavailableReason | None = None
    next_step: NextStep | None = None
    usage: CrossrefUsage | None = None

    @property
    def links(self) -> tuple[Verdict, ...]:
        """The ``link`` verdicts."""
        return tuple(v for v in self.verdicts if v.kind is VerdictKind.LINK)

    @property
    def written(self) -> tuple[str, ...]:
        """The stems this run wrote into the source's ``related:``."""
        return tuple(v.stem for v in self.verdicts if v.applied)


@dataclass(frozen=True)
class SweepOutcome:
    """The outcome of cross-referencing several sources in one bounded run.

    Attributes:
        outcomes: One outcome per source judged, in sweep order.
        remaining: Sources the selection held that this run did not reach.
        next_after: The last source judged, to resume after; ``None`` when
            the selection is exhausted.
        stopped: Why the sweep stopped early: the failure reason of the
            source that failed, ``deadline`` for the run deadline, or ``None``
            when it judged every source it took.
    """

    outcomes: tuple[CrossrefOutcome, ...] = ()
    remaining: int = 0
    next_after: str | None = None
    stopped: str | None = field(default=None)
