"""Search the vault: the one entry point every surface calls.

The service turns configuration and the vault on disk into one of the three
outcomes :class:`~vaultspec_core.search.SearchOutcome` defines, and owns the
decisions that sit above the ranking itself.

- **Input refused first.** A blank or overlong query and a record type
  search does not rank are refused before anything is read or sent, here
  rather than in each surface.
- **Nothing leaves without a key.** With no hosted-search credential the
  outcome is ``not_configured``: no client is built and no record is read for
  sending.
- **A decline names the way on.** Every ``not_configured`` and
  ``unavailable`` outcome carries the search to run instead, resolved from
  the requested record types and the workspace's companion provisioning.
- **Filters first.** The records are filtered in code before any request is
  built; when none survive, the answer is an empty ``ok`` that cost nothing.
- **One deadline.** Every request of a search shares one monotonic deadline,
  so a slow provider ends the search on time instead of per request.
- **All or nothing.** A provider failure other than a content rejection
  yields ``unavailable`` with its reason and never a partial ranking; a
  content rejection only leaves the records it refused unscored. When those
  refusals leave nothing ranked, the outcome is ``unavailable`` with
  ``content_rejected``: an empty ``ok`` page would read as "nothing answers"
  about records that were never read.
- **Bounded page.** The ranking is cut to the caller's limit, clamped to
  :data:`~vaultspec_core.search.MAX_RESULTS`, and the cut is described by the
  shared window vocabulary, so a caller always sees the total.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Final

from ..core.windowing import apply_window
from ._corpus import load_records
from ._credential import resolve_credential
from ._engine import WORKERS, Meter, run_search
from ._filters import record_types
from ._models import (
    DEFAULT_RESULTS,
    MAX_QUERY_CHARS,
    MAX_RESULTS,
    InvalidQueryError,
    SearchOutcome,
    SearchStatus,
    SearchUsage,
    UnavailableReason,
)
from ._remediation import next_step
from ._transport import HostedSearchError, JevClient

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping
    from pathlib import Path

    from ..vaultcore.models import DocType

__all__ = ["SEARCH_DEADLINE", "search_vault"]

#: Seconds one search may spend on the provider, across every request. A
#: search takes about a second; the rest is room for retries under load.
SEARCH_DEADLINE: Final = 25.0


def _page_size(limit: int) -> int:
    """Clamp *limit* into ``1..MAX_RESULTS``; a non-positive limit is the default."""
    if limit < 1:
        return DEFAULT_RESULTS
    return min(limit, MAX_RESULTS)


def _declined(
    root: Path,
    query: str,
    types: frozenset[DocType] | None,
    *,
    reason: UnavailableReason | None = None,
    usage: SearchUsage | None = None,
) -> SearchOutcome:
    """Build the outcome of a search that did not rank, with its next step.

    Args:
        root: The workspace root.
        query: The query as submitted.
        types: The record types the request named; ``None`` for all.
        reason: Why a configured search failed; ``None`` when no credential
            is configured.
        usage: What the failed search cost, when anything was sent.

    Returns:
        ``unavailable`` with *reason*, or ``not_configured`` without one.
    """
    status = SearchStatus.NOT_CONFIGURED if reason is None else SearchStatus.UNAVAILABLE
    return SearchOutcome(
        status=status,
        query=query,
        reason=reason,
        usage=usage,
        next_step=next_step(root, types),
    )


def search_vault(
    root: Path,
    query: str,
    *,
    doc_types: Collection[str] | None = None,
    feature: str | None = None,
    date: str | None = None,
    limit: int = DEFAULT_RESULTS,
    environ: Mapping[str, str] | None = None,
    client: JevClient | None = None,
) -> SearchOutcome:
    """Rank the vault's records against *query* and quote the answering passages.

    Args:
        root: The workspace root.
        query: The natural-language query.
        doc_types: Search only these record types, by name (a
            :class:`~vaultspec_core.vaultcore.models.DocType` is one);
            ``None`` or none searches every searchable type.
        feature: Search only this feature's records.
        date: Search only records with this exact date (``YYYY-MM-DD``).
        limit: Hits to return; clamped to ``1..MAX_RESULTS``, with a
            non-positive limit meaning the default.
        environ: The environment the credential is read from; ``None`` reads
            :data:`os.environ`.
        client: A client to use instead of building one from the credential;
            it is not closed here. A credential is still required.

    Returns:
        The outcome: ``ok`` with the ranked page, ``not_configured`` when no
        credential is available, or ``unavailable`` with its reason.

    Raises:
        InvalidQueryError: If *query* is blank or longer than
            :data:`MAX_QUERY_CHARS`.
        UnsearchableTypeError: If *doc_types* names a type search does not
            rank.
    """
    if not query.strip():
        raise InvalidQueryError("the search query must not be blank")
    if len(query) > MAX_QUERY_CHARS:
        raise InvalidQueryError(
            f"the search query must be at most {MAX_QUERY_CHARS} characters"
        )
    types = record_types(doc_types)
    credential = resolve_credential(root, environ)
    if credential is None:
        return _declined(root, query, types)
    records = load_records(root, doc_types=types, feature=feature, date=date)
    size = _page_size(limit)
    if not records:
        _, window = apply_window((), limit=size, pageable=False)
        return SearchOutcome(status=SearchStatus.OK, query=query, window=window)
    owned = client is None
    if client is None:
        try:
            client = JevClient(credential.key, max_concurrency=WORKERS)
        except ValueError:
            # A key no HTTP header can carry would be refused by the provider;
            # say so without sending it anywhere.
            return _declined(
                root, query, types, reason=UnavailableReason.CREDENTIAL_REJECTED
            )
    meter = Meter()
    try:
        ranking = run_search(
            client,
            query,
            records,
            deadline=time.monotonic() + SEARCH_DEADLINE,
            meter=meter,
        )
    except HostedSearchError as failure:
        if failure.reason is None:
            # Content rejections are absorbed by the engine as unscored
            # records; one reaching here is a defect, not an outcome.
            raise
        return _declined(root, query, types, reason=failure.reason, usage=meter.usage())
    finally:
        if owned:
            client.close()
    usage = meter.usage()
    if not ranking.hits and usage.unscored:
        return _declined(
            root, query, types, reason=UnavailableReason.CONTENT_REJECTED, usage=usage
        )
    hits, window = apply_window(ranking.hits, limit=size, pageable=False)
    return SearchOutcome(
        status=SearchStatus.OK,
        query=query,
        answered=ranking.answered,
        hits=tuple(hits),
        window=window,
        usage=usage,
    )
