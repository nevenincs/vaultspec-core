"""The words every search surface prints about an outcome.

The CLI prints them on the terminal and the MCP tool in its one-line
summary. Neither surface words an outcome itself, so both say the same thing
about the same result: which outcome it was, what the page says about the
vault, and which records or passages the search could not vouch for. The
next step after a decline is worded by :func:`~._remediation.remediation`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from ._models import SearchHit, SearchStatus, SearchVerdict, UnavailableReason

__all__ = ["NO_PASSAGE", "outcome_label", "premise_note", "unscored_note"]

#: Said of a ranked record for which no block was chosen as the answer.
NO_PASSAGE: Final = "no answering passage located"


def outcome_label(
    status: SearchStatus,
    verdict: SearchVerdict | None,
    reason: UnavailableReason | None,
) -> str:
    """Word which outcome a search produced.

    Args:
        status: The outcome.
        verdict: What a ranked page says about the vault; ``None`` unless
            the search ranked.
        reason: Why a configured search failed, if it did.

    Returns:
        The verdict's sentence for a ranked page, else the outcome's name
        with the failure reason: ``not configured`` or
        ``unavailable (rate_limited)``.
    """
    if verdict is not None:
        return verdict.sentence
    label = status.value.replace("_", " ")
    return label if reason is None else f"{label} ({reason.value})"


def unscored_note(unscored: int) -> str | None:
    """Word how many records went unread, which narrows the verdict.

    Args:
        unscored: Records the provider would not read in full.

    Returns:
        The count as a phrase, or ``None`` when every record was read.
    """
    if not unscored:
        return None
    noun = "record" if unscored == 1 else "records"
    return f"{unscored} {noun} the provider would not read in full"


def premise_note(hit: SearchHit) -> str | None:
    """Word a hit's likely contradiction of the question.

    Args:
        hit: A ranked record.

    Returns:
        The note with its probability, or ``None`` when the record likely
        does not contradict an assumption in the question.
    """
    if not hit.contradicts_premise:
        return None
    return f"may contradict an assumption in your question ({hit.premise_conflict:.2f})"
