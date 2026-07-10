"""Tests for the shared copied-context isolation wrapper.

These assert the wrapper's real guarantee: the handler *body* runs inside a
copied :class:`contextvars.Context`, so a contextvar mutation performed by a
handler never leaks back to the caller's context and two concurrent handlers
never observe each other's mutation. The regression these guard against is a
hollow ``ctx_copy.run(fn, ...)`` that only builds the coroutine in the copy
and then runs its body under the ambient context. No mocks, stubs, or skips:
real ``asyncio`` tasks over real :mod:`contextvars` state.
"""

from __future__ import annotations

import asyncio
import contextvars

import pytest

from vaultspec_core.mcp_server.isolation import isolated_context

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]

_probe: contextvars.ContextVar[str] = contextvars.ContextVar(
    "_probe", default="ambient"
)


async def test_handler_mutation_does_not_leak_to_caller() -> None:
    """A contextvar set inside a wrapped handler is invisible to the caller.

    The handler body must run in the copied context, so its ``set`` mutates
    only that copy. After awaiting the wrapped call the caller's ambient view
    of the same var must be unchanged.
    """

    @isolated_context
    async def handler() -> str:
        _probe.set("inside-handler")
        # The awaited yield point is where a hollow wrapper would run the body
        # in the ambient context; a real one keeps it in the copied context.
        await asyncio.sleep(0)
        return _probe.get()

    assert _probe.get() == "ambient"
    returned = await handler()
    # The handler observed its own mutation within its isolated context...
    assert returned == "inside-handler"
    # ...but the caller's ambient context never saw it.
    assert _probe.get() == "ambient"


async def test_concurrent_handlers_do_not_see_each_others_mutation() -> None:
    """Two handlers running concurrently each observe only their own write.

    Per-request isolation means the copied contexts are independent: each
    handler sets a distinct value, yields to let the other run, and must read
    back exactly its own value, never the sibling's.
    """

    started = asyncio.Event()

    @isolated_context
    async def handler(value: str, *, first: bool) -> str:
        _probe.set(value)
        if first:
            started.set()
            # Yield long enough for the sibling to set its own value.
            await started.wait()
            await asyncio.sleep(0)
        else:
            await started.wait()
            await asyncio.sleep(0)
        return _probe.get()

    first_read, second_read = await asyncio.gather(
        handler("first-value", first=True),
        handler("second-value", first=False),
    )

    assert first_read == "first-value"
    assert second_read == "second-value"
    # The caller's context is still pristine after both concurrent runs.
    assert _probe.get() == "ambient"
