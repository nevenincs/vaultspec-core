"""Execution-domain MCP tool: ``log``, the ledger writer.

A thin wrapper over :func:`vaultspec_core.vaultcore.exec_log.log_step`, the
same core the ``vault exec log`` CLI verb calls, so a Step logged through
either surface lands as the same rows in the same ledger. No row grammar or
plan resolution is authored here.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from ...core.types import get_context as _get_ctx
from ..envelope import LeanModel, compact_result
from ..isolation import isolated_context as _isolated_context

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

logger = logging.getLogger(__name__)

__all__ = ["LogResult", "register_exec_tools"]

#: The request context type the tool declares; the SDK resolves it at
#: registration, so the alias is bound at runtime rather than type-checking.
_ExecToolContext = Context[None, Any]


class LogResult(LeanModel):
    """The result of one ``log`` call.

    Attributes:
        path: The ledger's path relative to the project root.
        step: The canonical Step id the rows were logged under.
        rows: Count of ``## Changes`` rows offered for append.
        notes: Count of ``## Notes`` lines offered for append.
        changed: Whether the ledger changed; ``False`` on an idempotent re-log.
        created: Whether this call created the ledger.
    """

    path: str
    step: str
    rows: int
    notes: int
    changed: bool
    created: bool


def _log_summary(payload: object) -> str:
    """One-line summary of a :class:`LogResult` for the compact envelope."""
    if not isinstance(payload, dict):
        return str(payload)
    data = cast("dict[str, Any]", payload)
    verb = (
        "created"
        if data.get("created")
        else ("logged" if data.get("changed") else "unchanged")
    )
    return f"{verb}: {data.get('step')} -> {data.get('path')} ({data.get('rows')} rows)"


def register_exec_tools(mcp: MCPServer[None]) -> None:
    """Register the ``log`` tool on *mcp*.

    ``log`` is non-read-only, non-destructive (append-only), and idempotent
    (re-logging a row changes nothing).

    Args:
        mcp: The :class:`~mcp.server.mcpserver.MCPServer` instance to decorate.
    """

    @mcp.tool(
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        ),
    )
    @compact_result(_log_summary)
    @_isolated_context
    async def log(
        ctx: _ExecToolContext,
        feature: str,
        plan: str,
        step: str,
        rows: list[str] | None = None,
        verify: str | None = None,
        by: str | None = None,
        notes: list[str] | None = None,
    ) -> LogResult:
        """Append one Step's rows to its plan's execution ledger.

        Creates the ledger on first use; re-logging a row is idempotent.

        Args:
            ctx: The MCP request context (unused).
            feature: Feature tag.
            plan: The parent plan's stem.
            step: Step id (``S01``) or display path (``P01.S01``).
            rows: One ``OP:path`` per path touched: ``A:`` added, ``M:``
                modified, ``D:`` deleted, ``R:old->new`` renamed.
            verify: A check that ran, as ``<command>=pass|fail``.
            by: The persona that closed the Step.
            notes: Exception notes only.
        """
        _ = ctx
        from ...vaultcore.exec_log import (
            ExecLogError,
            LogRequest,
            log_step,
            parse_row_spec,
            parse_verify_spec,
        )

        root_dir = _get_ctx().target_dir
        try:
            request = LogRequest(
                feature=feature,
                plan_stem=plan,
                step=step,
                rows=tuple(parse_row_spec(spec) for spec in rows or []),
                verify=parse_verify_spec(verify) if verify else None,
                by=by,
                notes=tuple(notes or []),
            )
            outcome = log_step(root_dir, request)
        except ExecLogError as exc:
            raise ToolError(str(exc)) from exc

        logger.info("log: %s -> %s", outcome.step_id, outcome.path.name)
        return LogResult(
            path=str(outcome.path.relative_to(root_dir)),
            step=outcome.step_id,
            rows=len(outcome.rows),
            notes=len(outcome.notes),
            changed=outcome.changed,
            created=outcome.created,
        )

    _ = log  # bound by the decorator; silence unused warnings
