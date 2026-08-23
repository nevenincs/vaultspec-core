"""The compact-result wrapper that stops every tool payload shipping twice.

An MCPServer tool that declares a Pydantic return type gets an
``output_schema``, and the SDK's ``convert_result`` then builds *both* an
unstructured rendering and the structured payload from the same object and
returns them together (``func_metadata.py:132``).  For a ``list`` return it
is worse: ``_convert_to_content`` recurses and emits one ``indent=2`` text
block *per element* (``func_metadata.py:562``), so a twenty-row result ships
twenty pretty-printed JSON blocks alongside the structured array.

Measured against a 10,476-document vault before this module existed:

===========================  ============  ============  ============
call                         text bytes    struct bytes  duplicate
===========================  ============  ============  ============
``status``                        159,777       114,974          42%
``check``                         480,920       402,943          46%
``find`` (20 rows)                 13,413        12,225          48%
===========================  ============  ============  ============

The duplicate half is not a copy in the harmless sense - it is the *larger*
half, because the text rendering is pretty-printed while the structured
payload is not.  None of it reaches the model as information it did not
already receive.

The SDK sanctions the escape.  ``convert_result`` early-returns a
caller-supplied ``CallToolResult`` untouched, validating its
``structured_content`` against the output model but synthesising no text
(``func_metadata.py:126``).  So a tool may keep its declared return type -
and therefore its output schema - while returning the wire object itself.

:func:`compact_result` is that seam.  It wraps a tool coroutine so the
declared payload still flows into ``structured_content`` unchanged, and the
text channel carries one short human-readable line instead of a second copy.
``functools.wraps`` preserves ``__annotations__``, so MCPServer derives the
same ``output_schema`` from the same return type and the tool's wire
contract is unchanged apart from the text blocks.

The summary line is deliberately not a data channel.  It is what a human
tailing a transcript reads to see what happened; anything an agent must act
on belongs in the structured payload, where it is typed.
"""

from __future__ import annotations

import functools
import inspect
import re
from typing import TYPE_CHECKING, Any, ParamSpec, Protocol, TypeVar, cast

from mcp.types import CallToolResult, TextContent
from pydantic import BaseModel
from pydantic_core import to_jsonable_python

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

__all__ = ["compact_result", "describe", "tool_description"]

_P = ParamSpec("_P")
_R = TypeVar("_R")

#: Hard cap on the summary line.  A summary that grows with the payload would
#: reintroduce the defect this module exists to remove, so the cap is on the
#: rendered string rather than on the caller's good intentions.
_MAX_SUMMARY_CHARS = 200


class _Summariser(Protocol):
    """Renders a tool's payload as one short human-readable line."""

    def __call__(self, payload: Any, /) -> str: ...


#: Docstring sections that never reach the model as usable guidance.
#:
#: ``Returns:`` restates what ``output_schema`` already carries, and names
#: Python classes the model cannot see. ``Raises:`` describes exceptions it
#: never observes - a protocol error arrives as an error result, not a
#: traceback. Both are maintainer documentation that the SDK lifts verbatim
#: into the tool description re-sent on every turn of every conversation.
_DROPPED_SECTIONS = ("Returns:", "Raises:", "Yields:")

#: Matches the ``ctx`` entry inside an ``Args:`` block.
#:
#: ``ctx`` is the MCP request context: a parameter of the Python function that
#: appears in no ``inputSchema``, so documenting it describes an argument the
#: model cannot pass. Two tools spend a full sentence explaining it is unused.
_CTX_ARG = re.compile(r"\n\s*ctx:.*?(?=\n\s{8}\w+:|\Z)", re.S)

#: An ``Args:`` heading left with nothing under it after the ctx removal.
_EMPTY_ARGS = re.compile(r"\n\s*Args:\s*(?=\Z)")


def tool_description(fn: object) -> str:
    """Return *fn*'s docstring trimmed to what the model can act on.

    The summary and the per-parameter guidance survive; the sections that
    duplicate the schema or describe machinery the caller never touches do
    not. Applied at registration, so the docstring stays intact in source for
    whoever maintains the function.

    Args:
        fn: The tool function whose docstring becomes the tool description.

    Returns:
        The trimmed description text.
    """
    doc = inspect.getdoc(fn) or ""
    for marker in _DROPPED_SECTIONS:
        idx = doc.find("\n" + marker)
        if idx != -1:
            doc = doc[:idx]
    doc = _CTX_ARG.sub("", doc)
    doc = _EMPTY_ARGS.sub("", doc)
    return doc.strip()


def _structured(payload: object) -> Any:
    """Render *payload* the way the SDK would for ``structured_content``.

    Mirrors ``_try_create_model_and_schema``'s wrapping rule: a ``BaseModel``
    return type maps to the object itself, while any other shape (notably the
    ``list`` returns) is wrapped in ``{"result": ...}``.  Getting this wrong
    would surface as an output-schema validation error at call time rather
    than silently, because the SDK validates what we hand it.

    Args:
        payload: The value the tool function returned.

    Returns:
        The JSON-ready structured content for the wire result.
    """
    if isinstance(payload, BaseModel):
        return payload.model_dump(mode="json", by_alias=True)
    return {"result": to_jsonable_python(payload, by_alias=True)}


def describe(payload: object) -> str:
    """Summarise *payload* in one line without walking its contents.

    The default used when a tool does not supply its own summariser.  It
    reports shape, never content: a count for a sequence, the status field
    for a result model that carries one, the type name otherwise.  Walking
    the payload to say something more specific would cost time proportional
    to the thing we are trying not to serialise.

    Args:
        payload: The value the tool function returned.

    Returns:
        A short description of the payload's shape.
    """
    if isinstance(payload, list):
        rows: list[object] = cast("list[object]", payload)
        return f"{len(rows)} row{'' if len(rows) == 1 else 's'}"
    if isinstance(payload, BaseModel):
        status = getattr(payload, "status", None)
        name = type(payload).__name__
        return f"{name}: {status}" if isinstance(status, str) else name
    return type(payload).__name__


def compact_result(
    summarise: _Summariser | None = None,
) -> Callable[
    [Callable[_P, Awaitable[_R]]],
    Callable[_P, Awaitable[_R]],
]:
    """Wrap a tool coroutine so its payload is serialised once, not twice.

    The wrapped coroutine returns a ``CallToolResult`` at runtime while
    keeping the inner function's return annotation, so MCPServer still
    derives the tool's ``output_schema`` from the declared type. The declared
    return type is therefore preserved in the signature even though the wire
    object differs - that divergence is the whole mechanism, and the SDK
    accommodates it explicitly.

    Args:
        summarise: Renders the one-line text summary. Defaults to
            :func:`describe`, which reports shape only.

    Returns:
        A decorator that adapts a tool coroutine in place.
    """
    render: _Summariser = summarise or describe

    def decorator(fn: Callable[_P, Awaitable[_R]]) -> Callable[_P, Awaitable[_R]]:
        @functools.wraps(fn)
        async def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> Any:
            payload = await fn(*args, **kwargs)
            try:
                summary = render(payload)
            except Exception:
                summary = describe(payload)
            return CallToolResult(
                content=[TextContent(type="text", text=summary[:_MAX_SUMMARY_CHARS])],
                structured_content=_structured(payload),
            )

        wrapper.__doc__ = tool_description(fn)
        return wrapper

    return decorator
