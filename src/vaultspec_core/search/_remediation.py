"""What a caller should do when hosted search did not run or did not finish.

Every surface that reports a search outcome - the MCP tool, the CLI verb -
tells the caller the same next step, so the sentences live here once rather
than in each surface. Each names the concrete action and the fallback: the
agent-level route to vaultspec-rag in its canonical spelling, never a proxy
call, because core does not call rag.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from ..core.discovery_guidance import SEARCH_ADR
from ._credential import CREDENTIAL_VARIABLE
from ._models import SearchStatus, UnavailableReason

if TYPE_CHECKING:
    from ._models import SearchOutcome

__all__ = ["remediation"]

_FALLBACK: Final = f"or search with {SEARCH_ADR}."

_UNAVAILABLE: Final[dict[UnavailableReason, str]] = {
    UnavailableReason.CREDENTIAL_REJECTED: (
        f"The TypeSafe API rejected the key in {CREDENTIAL_VARIABLE} or denied "
        f"it this request; check or rotate it, {_FALLBACK}"
    ),
    UnavailableReason.CONTENT_REJECTED: (
        "The TypeSafe API refused to read the query or every record it matched; "
        f"rephrase the query or narrow it with type or feature filters, {_FALLBACK}"
    ),
    UnavailableReason.RATE_LIMITED: (
        f"The TypeSafe API is rate limiting this key; retry shortly, {_FALLBACK}"
    ),
    UnavailableReason.TRANSPORT: (
        f"The TypeSafe API could not be reached; retry, {_FALLBACK}"
    ),
    UnavailableReason.DEADLINE: (
        "Hosted search ran out of time; retry with type or feature filters, "
        f"{_FALLBACK}"
    ),
    UnavailableReason.INVALID_RESPONSE: (
        f"The TypeSafe API returned a response search could not use; retry, {_FALLBACK}"
    ),
    UnavailableReason.REQUEST_TOO_LARGE: (
        "A record exceeded the provider's request size; narrow the search with "
        f"type or feature filters, {_FALLBACK}"
    ),
}

_NOT_CONFIGURED: Final = (
    f"Hosted vault search is not configured: set {CREDENTIAL_VARIABLE} to enable "
    f"it, {_FALLBACK}"
)


def remediation(outcome: SearchOutcome) -> str | None:
    """Return the next step for a search that did not produce a ranking.

    Args:
        outcome: A search outcome.

    Returns:
        One sentence for ``not_configured`` and ``unavailable`` outcomes, or
        ``None`` for ``ok``, which needs none.
    """
    if outcome.status is SearchStatus.NOT_CONFIGURED:
        return _NOT_CONFIGURED
    if outcome.status is SearchStatus.UNAVAILABLE:
        reason = outcome.reason or UnavailableReason.TRANSPORT
        return _UNAVAILABLE[reason]
    return None
