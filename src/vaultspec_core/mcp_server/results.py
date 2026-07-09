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
FastMCP derives an ``outputSchema`` from the tool return type and returns
``structuredContent`` to the host.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

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


class ItemResult(BaseModel):
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


class BatchResult(BaseModel):
    """The whole-call result of a batch ``create`` or ``edit`` invocation.

    A partially-failed batch is a *successful* call: it returns
    ``status == "mixed"`` and reports each item's outcome, rather than
    surfacing a protocol error.  Whole-call failures (malformed arguments)
    raise before a :class:`BatchResult` is ever built.

    Attributes:
        status: The aggregate outcome - ``ok`` when every item succeeded,
            ``failed`` when every item failed, ``mixed`` when they disagree.
        items: The per-item results in submission order.
    """

    status: str
    items: list[ItemResult]


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


def build_batch(items: list[ItemResult]) -> BatchResult:
    """Wrap per-item results in a :class:`BatchResult` with the aggregate status.

    Args:
        items: The per-item results in submission order.

    Returns:
        The :class:`BatchResult` carrying the reduced aggregate status.
    """
    return BatchResult(status=reduce_status(items), items=items)
