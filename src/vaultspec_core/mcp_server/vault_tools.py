"""Register the vault ``find`` MCP tool on a FastMCP instance.

Exposes ``find`` for vault document discovery and feature listing (with
graph-based weight scoring), delegating to the vault query engine and
:class:`~vaultspec_core.graph.VaultGraph`.  The document-mutation tools
(``create`` / ``edit``) live in
:mod:`vaultspec_core.mcp_server.tools.documents`; register them via
:func:`~vaultspec_core.mcp_server.tools.register_document_tools`.

Call :func:`register_tools` to attach ``find`` to a ``FastMCP`` instance
before serving the MCP endpoint.
"""

from __future__ import annotations

import contextvars
import functools
import logging
from typing import TYPE_CHECKING, Any

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from mcp.server.fastmcp import FastMCP

from ..core.types import get_context as _get_ctx

logger = logging.getLogger(__name__)

__all__ = ["register_tools"]


def _isolated_context(
    fn: Callable[..., Coroutine[Any, Any, Any]],
) -> Callable[..., Coroutine[Any, Any, Any]]:
    """Wrap an async tool handler so it runs in a copied context.

    Each invocation snapshots all :mod:`contextvars` state via
    :func:`contextvars.copy_context` and invokes the handler inside that
    snapshot.  This prevents mutations from leaking between concurrent
    MCP requests without the race-prone manual save/restore pattern.
    """

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        ctx_copy = contextvars.copy_context()
        coro = ctx_copy.run(fn, *args, **kwargs)
        return await coro

    return wrapper


_DEFAULT_TYPES = ["adr", "plan", "research", "reference"]


def _infer_status(types: set[str]) -> str:
    """Infer lifecycle status from the set of document types present."""
    if "exec" in types:
        return "In Progress"
    if "plan" in types:
        return "Planned"
    if "adr" in types:
        return "Specified"
    if "research" in types:
        return "Researching"
    return "Unknown"


def register_tools(mcp: FastMCP) -> None:
    """Register the ``find`` vault tool on *mcp*.

    ``find``  - read-only, idempotent tool for feature listing and document
    search with graph-weight scoring via :class:`~vaultspec_core.graph.VaultGraph`.

    Args:
        mcp: :class:`~mcp.server.fastmcp.FastMCP` instance to decorate.
    """

    @mcp.tool(
        annotations=ToolAnnotations(
            readOnlyHint=True,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    @_isolated_context
    async def find(
        ctx: Context,
        feature: str | None = None,
        type: list[str] | None = None,
        date: str | None = None,
        body: bool = False,
        json: bool = False,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Find vault documents or list features.

        With no arguments, returns all features with document count and
        graph weight score.  Add filters to narrow to specific documents.

        The ``type`` filter defaults to adr, plan, research, reference.
        Exec and audit entries are excluded unless explicitly requested.
        """
        from ..graph import VaultGraph
        from ..vaultcore.query import list_documents, list_feature_details

        await ctx.info(
            f"find: feature={feature!r} type={type!r} date={date!r} "
            f"body={body} json={json} limit={limit}"
        )

        # --- Feature listing mode (no filters) ---
        if not feature and not type and not date:
            features = list_feature_details(_get_ctx().target_dir)
            graph_unavailable = False
            try:
                graph = VaultGraph(_get_ctx().target_dir)
                rankings = dict(graph.get_feature_rankings(limit=100))
            except (OSError, ValueError) as exc:
                logger.warning("Failed to load vault graph rankings: %s", exc)
                rankings = {}
                graph_unavailable = True

            results = []
            for feat in features[:limit]:
                entry: dict[str, Any] = {
                    "name": feat["name"],
                    "doc_count": feat["doc_count"],
                    "weight": rankings.get(feat["name"], 0),
                }
                if graph_unavailable:
                    entry["_note"] = "graph ranking unavailable"
                if json:
                    entry["status"] = _infer_status(set(feat["types"]))
                    entry["types"] = feat["types"]
                    entry["earliest_date"] = feat["earliest_date"]
                    entry["has_plan"] = feat["has_plan"]
                results.append(entry)

            await ctx.debug(f"Listed {len(results)} features.")
            return results

        # --- Document search mode ---
        effective_types = type if type else _DEFAULT_TYPES

        all_docs = []
        for dt in effective_types:
            docs = list_documents(
                _get_ctx().target_dir,
                doc_type=dt,
                feature=feature,
                date=date,
            )
            all_docs.extend(docs)

        results = []
        for doc in all_docs[:limit]:
            entry: dict[str, Any] = {
                "name": doc.name,
                "type": doc.doc_type,
                "feature": doc.feature,
                "date": doc.date,
                "path": str(doc.path.relative_to(_get_ctx().target_dir)),
            }
            if body:
                try:
                    entry["body"] = doc.path.read_text(encoding="utf-8")
                except Exception:
                    logger.warning(
                        "Failed to read body of %s",
                        entry.get("name", "unknown"),
                    )
                    entry["body"] = ""
            results.append(entry)

        await ctx.debug(f"Found {len(results)} documents.")
        return results
