"""The unified per-item result envelope shared by the batch MCP tools.

The ``create`` and ``edit`` tools are batch-native: each takes a list of
work items and applies them sequentially, and item failures do not abort
the batch.  Both surface their outcome through the one shape defined here -
a list of :class:`ItemResult` wrapped in a :class:`BatchResult` whose
aggregate ``status`` folds the per-item outcomes into the CLI's canonical
sync-envelope vocabulary (``ok`` / ``mixed`` / ``failed``).

Speaking the CLI's result language on the MCP surface is deliberate: an
agent that already reads ``created`` / ``updated`` / ``unchanged`` /
``failed`` from ``vaultspec-core ... --json`` reads the same words here, and
the aggregate reducer matches the CLI's rule that a batch is ``mixed`` only
when its items disagree.  The models are Pydantic ``BaseModel`` subclasses so
MCPServer derives an ``output_schema`` from the tool return type and returns
``structured_content`` to the host.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from .envelope import LeanModel

__all__ = [
    "BatchResult",
    "ItemResult",
    "build_batch",
    "build_item",
    "reduce_status",
]

#: Per-item statuses that count as a successful application. ``unchanged`` is
#: a successful no-op (a set-body that matched the on-disk bytes), not a
#: failure - the same reading the CLI sync envelope gives it.
_SUCCESS_STATUSES = frozenset({"created", "updated", "unchanged"})


class ItemResult(LeanModel):
    """The outcome of one item in a batch ``create`` or ``edit`` call.

    Attributes:
        index: The item's zero-based position in the submitted batch, so a
            caller can correlate a result with its request and resubmit only
            the failed items.
        target: The item's address as submitted (a document stem or path for
            ``edit``, a ``type:feature`` descriptor for ``create``), echoed
            for traceability.
        status: The canonical per-item outcome word - ``created`` /
            ``updated`` / ``unchanged`` on success, ``failed`` otherwise.
        path: The affected document path relative to the project root on
            success; ``None`` when no file was resolved or written.
        blob_hash: The git blob OID of the post-write bytes on success, so a
            subsequent edit chains from it without a re-read; ``None`` on
            failure.
        error: The structured failure payload on ``failed`` (carrying
            ``message`` plus any of ``conflict`` / ``refused`` / ``checks`` /
            ``section_not_found``); ``None`` on success.
        warnings: Advisory messages (e.g. missing-ADR lifecycle warnings)
            that did not block the item.
    """

    index: int
    target: str | None = None
    status: str
    path: str | None = None
    blob_hash: str | None = None
    error: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)


class BatchResult(LeanModel):
    """The whole-call result of a batch ``create`` or ``edit`` invocation.

    A partially-failed batch is a *successful* call: it returns
    ``status == "mixed"`` and reports each item's outcome, rather than
    surfacing a protocol error.  Whole-call failures (malformed arguments)
    raise before a :class:`BatchResult` is ever built.

    Attributes:
        status: The aggregate outcome - ``ok`` when every item succeeded,
            ``failed`` when every item failed, ``mixed`` when they disagree.
        items: The rows a caller must read - every failure and every item
            carrying a warning, plus a sample of plain successes.
        counts: How many items landed in each status. Exact regardless of
            how many rows were omitted, so a caller always knows the true
            outcome of the batch.
        submitted: Items in the submitted batch.
        items_omitted: Uneventful successes not enumerated. A batch that
            wholly succeeded costs about the same at 5,000 items as at 20.
    """

    status: str
    items: list[ItemResult]
    counts: dict[str, int] = Field(default_factory=dict)
    submitted: int = 0
    items_omitted: int = 0


def build_item(
    index: int,
    *,
    status: str,
    target: str | None = None,
    path: str | None = None,
    blob_hash: str | None = None,
    error: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
) -> ItemResult:
    """Assemble a single :class:`ItemResult` for a batch entry.

    Args:
        index: The item's zero-based position in the submitted batch.
        status: The canonical per-item outcome (``created`` / ``updated`` /
            ``unchanged`` / ``failed``).
        target: The item's submitted address, echoed for traceability.
        path: The affected document path relative to the project root.
        blob_hash: The post-write git blob OID on success.
        error: The structured failure payload on ``failed``.
        warnings: Advisory messages that did not block the item.

    Returns:
        The populated :class:`ItemResult`.
    """
    return ItemResult(
        index=index,
        target=target,
        status=status,
        path=path,
        blob_hash=blob_hash,
        error=error,
        warnings=list(warnings) if warnings else [],
    )


def reduce_status(items: list[ItemResult]) -> str:
    """Fold per-item statuses into the aggregate ``ok`` / ``mixed`` / ``failed``.

    Mirrors the CLI sync-envelope aggregate: every item succeeding is
    ``ok``, every item failing is ``failed``, and any disagreement is
    ``mixed``.  An empty batch is treated as ``ok`` (a vacuous success),
    though the batch tools reject an empty input as a whole-call error
    before reaching this reducer.

    Args:
        items: The per-item results to aggregate.

    Returns:
        The aggregate status word.
    """
    if not items:
        return "ok"
    successes = sum(1 for item in items if item.status in _SUCCESS_STATUSES)
    if successes == len(items):
        return "ok"
    if successes == 0:
        return "failed"
    return "mixed"


#: Items a single batch may carry.
#:
#: A rejection names the limit; an unbounded batch instead detonates the
#: caller's context on the way back, having already applied every write. The
#: cap is on input so the failure arrives before any file is touched.
MAX_BATCH_ITEMS = 200

#: Successful items enumerated in a response.
#:
#: A batch response was one row per submitted item, unconditionally - a
#: 5,000-item batch cost roughly 2.4 MB to say "updated" five thousand times,
#: with each row echoing data the caller had just sent. Failures and warnings
#: are always enumerated in full, because those are what a caller must act on;
#: uneventful successes collapse into the counts.
MAX_ENUMERATED_SUCCESSES = 20


def build_batch(items: list[ItemResult]) -> BatchResult:
    """Fold per-item results into the batch response.

    The response is exception-based. Every failed item and every item carrying
    a warning is enumerated, because those are the rows a caller has to read.
    Plain successes are summarised in ``counts`` and the first few are kept as
    a sample, so a wholly successful batch of any size costs about the same as
    a small one.

    Args:
        items: The per-item outcomes, in submission order.

    Returns:
        The assembled :class:`BatchResult`.
    """
    counts: dict[str, int] = {}
    for item in items:
        counts[item.status] = counts.get(item.status, 0) + 1

    notable = [item for item in items if item.status == "failed" or item.warnings]
    uneventful = [
        item for item in items if item.status != "failed" and not item.warnings
    ]
    kept = notable + uneventful[:MAX_ENUMERATED_SUCCESSES]
    kept.sort(key=lambda item: item.index)

    return BatchResult(
        status=reduce_status(items),
        items=kept,
        counts=counts,
        submitted=len(items),
        items_omitted=len(items) - len(kept),
    )
