"""Search the vault: the one entry point every surface calls.

The service turns configuration and the vault on disk into one of the three
outcomes :class:`~vaultspec_core.search.SearchOutcome` defines, and owns the
decisions that sit above the ranking itself.

- **Nothing leaves without a key.** With no hosted-search credential the
  outcome is ``not_configured``: no client is built, no record is read for
  sending, and the caller routes to the agent-level fallback.
- **Filters first.** The records are filtered in code before any request is
  built; when none survive, the answer is an empty ``ok`` that cost nothing.
- **One deadline.** Every request of a search shares one monotonic deadline,
  so a slow provider ends the search on time instead of per request.
- **All or nothing.** A provider failure other than a content rejection
  yields ``unavailable`` with its reason and never a partial ranking; a
  content rejection only leaves the records it refused unscored.
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
from ._models import (
    DEFAULT_RESULTS,
    MAX_QUERY_CHARS,
    MAX_RESULTS,
    SearchOutcome,
    SearchStatus,
    UnavailableReason,
)
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


def search_vault(
    root: Path,
    query: str,
    *,
    doc_types: Collection[DocType] | None = None,
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
        doc_types: Search only these record types; ``None`` searches every
            searchable type.
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
        ValueError: If *query* is blank or longer than :data:`MAX_QUERY_CHARS`.
    """
    if not query.strip():
        raise ValueError("the search query must not be blank")
    if len(query) > MAX_QUERY_CHARS:
        raise ValueError(
            f"the search query must be at most {MAX_QUERY_CHARS} characters"
        )
    credential = resolve_credential(root, environ)
    if credential is None:
        return SearchOutcome(status=SearchStatus.NOT_CONFIGURED, query=query)
    records = load_records(root, doc_types=doc_types, feature=feature, date=date)
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
            return SearchOutcome(
                status=SearchStatus.UNAVAILABLE,
                query=query,
                reason=UnavailableReason.CREDENTIAL_REJECTED,
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
        return SearchOutcome(
            status=SearchStatus.UNAVAILABLE,
            query=query,
            reason=failure.reason,
            usage=meter.usage(),
        )
    finally:
        if owned:
            client.close()
    hits, window = apply_window(ranking.hits, limit=size, pageable=False)
    return SearchOutcome(
        status=SearchStatus.OK,
        query=query,
        answered=ranking.answered,
        hits=tuple(hits),
        window=window,
        usage=meter.usage(),
    )
