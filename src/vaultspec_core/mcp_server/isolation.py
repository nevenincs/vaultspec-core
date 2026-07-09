"""Concurrent-request isolation wrapper shared by every MCP tool handler.

Each tool handler runs inside a copied :class:`contextvars.Context` so that
per-request path mutations (the ``init_paths`` globals resolved from the
server root) never leak between concurrent MCP requests.  The wrapper is a
single shared definition rather than one copy per tool module, so the
concurrency guarantee is stated in exactly one place and the ADR constraint
"concurrent-request isolation via the copied-context wrapper is retained on
every handler" cannot drift between modules.

The isolation is real for the ``async def`` handlers this wraps.  Running an
async function through :meth:`contextvars.Context.run` only *constructs* the
coroutine inside the copied context; its body would then execute under the
ambient context at ``await`` time, so a bare ``ctx_copy.run(fn, ...)`` gives
no per-request isolation at all.  The wrapper instead creates the task
*inside* the copied context, so the task adopts that context and the handler
body - every ``await`` point included - runs isolated from the caller.
"""

from __future__ import annotations

import asyncio
import contextvars
import functools
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

__all__ = ["isolated_context"]


def isolated_context(
    fn: Callable[..., Coroutine[Any, Any, Any]],
) -> Callable[..., Coroutine[Any, Any, Any]]:
    """Wrap an async tool handler so its body runs in a copied context.

    Each invocation snapshots all :mod:`contextvars` state via
    :func:`contextvars.copy_context`, then schedules the handler coroutine as
    a task *created inside* that snapshot so the task adopts the copied
    context.  The handler body therefore executes - across every ``await``
    point - in the isolated copy, so per-request path mutations never leak
    back to the caller's context or across concurrent MCP requests, without
    the race-prone manual save/restore pattern.

    Args:
        fn: The async tool handler to wrap.

    Returns:
        The wrapped handler whose body executes in an isolated context copy.
    """

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        ctx_copy = contextvars.copy_context()
        coro = fn(*args, **kwargs)
        # Creating the task inside the copied context makes the task adopt it,
        # so the coroutine *body* runs isolated. Awaiting a coroutine built via
        # ``ctx_copy.run(fn, ...)`` would instead run the body in the ambient
        # context, defeating per-request isolation.
        task = ctx_copy.run(asyncio.ensure_future, coro)
        return await task

    return wrapper
