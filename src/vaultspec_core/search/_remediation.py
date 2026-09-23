"""What a caller should do when hosted search did not run or did not finish.

Every surface that reports a search outcome - the MCP tool, the CLI verb -
tells the caller the same next step, so it is resolved and worded here once
rather than in each surface.

- **Resolved, not assumed.** The next step is a vaultspec-rag vault search
  over the requested record types, feature and date when the workspace
  provisions the rag companion, and core's listing verbs plus grep otherwise.
  Provisioning is read from the companion probe, which reads configuration
  only: core names the rag search and never calls rag.
- **Typed, then worded.** The step travels as a :class:`NextStep` in the
  outcome, and :func:`remediation` words it after the reason hosted search
  did not rank.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from ..config import VAULTSPEC_CORE_TYPESAFE_API_KEY
from ..core.discovery_guidance import LIST_VAULT, RAG_VAULT_SEARCH
from ..core.enums import DirName
from ..vaultcore.normalize import normalize_feature_tag, normalize_vault_date
from ._corpus import SEARCHABLE_TYPES
from ._models import NextStep, NextStepKind, SearchStatus, UnavailableReason

if TYPE_CHECKING:
    from pathlib import Path

    from ..vaultcore.models import DocType
    from ._models import SearchOutcome

__all__ = ["next_step", "remediation"]

_UNAVAILABLE: Final[dict[UnavailableReason, str]] = {
    UnavailableReason.CREDENTIAL_REJECTED: (
        "The TypeSafe API rejected the key in "
        f"{VAULTSPEC_CORE_TYPESAFE_API_KEY.env_name} or denied "
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
    "Hosted vault search is not configured: set "
    f"{VAULTSPEC_CORE_TYPESAFE_API_KEY.env_name} to enable it"
)


def _scope_flags(feature: str | None, date: str | None) -> str:
    """Spell the feature and date filters as flags both next steps accept.

    The rag vault search and the listing verb each take ``--feature`` and
    ``--date``. Only a well-formed tag or calendar date is carried, in its
    normalized form, so a filter never places arbitrary text in a command a
    caller runs; a malformed one matches no record anyway.
    """
    flags = ""
    if feature is not None:
        tag = normalize_feature_tag(feature)
        if tag.ok:
            flags += f" --feature {tag.value}"
    if date is not None:
        day = normalize_vault_date(date)
        if day.ok:
            flags += f" --date {day.value}"
    return flags


def next_step(
    root: Path,
    types: frozenset[DocType] | None,
    *,
    feature: str | None = None,
    date: str | None = None,
) -> NextStep:
    """Resolve the search to run in place of hosted search.

    Args:
        root: The workspace root, whose companion provisioning is read.
        types: The record types the request named; ``None`` for all of them.
        feature: The feature filter the request named, if any.
        date: The date filter the request named, if any.

    Returns:
        A rag vault search over *types* when the rag companion is
        provisioned, else core's listing verb for them, each narrowed by the
        request's feature and date.
    """
    from ..core.diagnosis.collectors_companion import probe_companion

    covered = tuple(sorted(types or SEARCHABLE_TYPES))
    scope = _scope_flags(feature, date)
    companion = probe_companion(root)
    if companion is not None and companion.provisioned:
        return NextStep(
            kind=NextStepKind.RAG_SEARCH,
            types=covered,
            command=f"{RAG_VAULT_SEARCH} --doc-type {','.join(covered)}{scope}",
        )
    # The listing verb takes one type; several are listed together.
    listed = f"{LIST_VAULT} {covered[0]}" if len(covered) == 1 else LIST_VAULT
    return NextStep(kind=NextStepKind.LISTING, types=covered, command=listed + scope)


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
