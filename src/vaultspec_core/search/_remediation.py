"""What a caller should do when hosted search did not run or did not finish.

Every surface that reports a search outcome - the MCP tool, the CLI verb -
tells the caller the same next step, so it is resolved and worded here once
rather than in each surface.

- **Resolved, not assumed.** The next step is a vaultspec-rag vault search
  over the requested record types when the workspace provisions the rag
  companion, and core's listing verbs plus grep otherwise. Provisioning is
  read from the companion probe, which reads configuration only: core names
  the rag search and never calls rag.
- **Typed, then worded.** The step travels as a :class:`NextStep` in the
  outcome, and :func:`remediation` words it after the reason hosted search
  did not rank.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from ..core.discovery_guidance import LIST_VAULT, RAG_VAULT_SEARCH
from ..core.enums import DirName
from ._corpus import SEARCHABLE_TYPES
from ._credential import CREDENTIAL_VARIABLE
from ._models import NextStep, NextStepKind, SearchStatus, UnavailableReason

if TYPE_CHECKING:
    from pathlib import Path

    from ..vaultcore.models import DocType
    from ._models import SearchOutcome

__all__ = ["next_step", "remediation"]

_UNAVAILABLE: Final[dict[UnavailableReason, str]] = {
    UnavailableReason.CREDENTIAL_REJECTED: (
        f"The TypeSafe API rejected the key in {CREDENTIAL_VARIABLE} or denied "
        "it this request; check or rotate it"
    ),
    UnavailableReason.CONTENT_REJECTED: (
        "The TypeSafe API refused to read the query or every record it matched; "
        "rephrase the query or narrow it with type or feature filters"
    ),
    UnavailableReason.RATE_LIMITED: (
        "The TypeSafe API is rate limiting this key; retry shortly"
    ),
    UnavailableReason.TRANSPORT: "The TypeSafe API could not be reached; retry",
    UnavailableReason.DEADLINE: (
        "Hosted search ran out of time; retry with type or feature filters"
    ),
    UnavailableReason.INVALID_RESPONSE: (
        "The TypeSafe API returned a response search could not use; retry"
    ),
    UnavailableReason.REQUEST_TOO_LARGE: (
        "A record exceeded the provider's request size; narrow the search with "
        "type or feature filters"
    ),
}

_NOT_CONFIGURED: Final = (
    f"Hosted vault search is not configured: set {CREDENTIAL_VARIABLE} to enable it"
)


def next_step(root: Path, types: frozenset[DocType] | None) -> NextStep:
    """Resolve the search to run in place of hosted search.

    Args:
        root: The workspace root, whose companion provisioning is read.
        types: The record types the request named; ``None`` for all of them.

    Returns:
        A rag vault search over *types* when the rag companion is
        provisioned, else core's listing verb for them.
    """
    from ..core.diagnosis.collectors_companion import probe_companion

    covered = tuple(sorted(types or SEARCHABLE_TYPES))
    companion = probe_companion(root)
    if companion is not None and companion.provisioned:
        return NextStep(
            kind=NextStepKind.RAG_SEARCH,
            types=covered,
            command=f"{RAG_VAULT_SEARCH} --doc-type {','.join(covered)}",
        )
    # The listing verb takes one type; several are listed together.
    listed = f"{LIST_VAULT} {covered[0]}" if len(covered) == 1 else LIST_VAULT
    return NextStep(kind=NextStepKind.LISTING, types=covered, command=listed)


def _fallback(step: NextStep) -> str:
    """Word *step* as the clause that closes a remediation sentence."""
    if step.kind is NextStepKind.RAG_SEARCH:
        return f"or run `{step.command}`."
    scope = f"{DirName.VAULT}/"
    if len(step.types) == 1:
        scope += f"{step.types[0]}/"
    return (
        f"or list the records with `{step.command}` (MCP: `find`) and grep "
        f"`{scope}` for the passage."
    )


def remediation(outcome: SearchOutcome) -> str | None:
    """Return the next step for a search that did not produce a ranking.

    Args:
        outcome: A search outcome.

    Returns:
        One sentence for ``not_configured`` and ``unavailable`` outcomes: why
        hosted search did not rank, then the search to run instead. ``None``
        for ``ok``, which needs none.
    """
    if outcome.next_step is None:
        return None
    if outcome.status is SearchStatus.NOT_CONFIGURED:
        cause = _NOT_CONFIGURED
    else:
        cause = _UNAVAILABLE[outcome.reason or UnavailableReason.TRANSPORT]
    return f"{cause}, {_fallback(outcome.next_step)}"
