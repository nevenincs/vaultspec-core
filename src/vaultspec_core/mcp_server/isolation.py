"""Concurrent-request isolation wrapper shared by every MCP tool handler.

Each tool handler runs inside a copied :class:`contextvars.Context` so that
per-request path mutations (the ``init_paths`` globals resolved from the
server root) never leak between concurrent MCP requests.  The wrapper is a
single shared definition rather than one copy per tool module, so the
concurrency guarantee is stated in exactly one place and the ADR constraint
"concurrent-request isolation via the copied-context wrapper is retained on
every handler" cannot drift between modules.
"""

from __future__ import annotations

import contextvars
import functools
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

__all__ = ["isolated_context"]


def isolated_context(
    fn: Callable[..., Coroutine[Any, Any, Any]],
) -> Callable[..., Coroutine[Any, Any, Any]]:
    """Wrap an async tool handler so it runs in a copied context.

    Each invocation snapshots all :mod:`contextvars` state via
    :func:`contextvars.copy_context` and runs the handler inside that
    snapshot, so per-request path mutations never leak between concurrent
    MCP requests without the race-prone manual save/restore pattern.

    Args:
        fn: The async tool handler to wrap.

    Returns:
        The wrapped handler that executes in an isolated context copy.
    """

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        ctx_copy = contextvars.copy_context()
        coro = ctx_copy.run(fn, *args, **kwargs)
        return await coro

    return wrapper
