"""Every tool's reply validates against the output schema it publishes.

The schema decides which keys publish a ``null`` branch from the model's
``required`` list, and the wire decides which ``None`` values it prunes from
``is_required()``. Nothing ties the two together, so this guard generates
replies from each tool's declared result type, with every nullable value
``None``, renders them the way the wire does, and validates each against the
published schema. Replies are built from the models' own annotations, so a
new field or result model is covered without editing this file.
"""

from __future__ import annotations

import dataclasses
import enum
import types
import typing
from typing import TYPE_CHECKING, Any, Literal, cast

import pytest
from jsonschema.validators import validator_for
from pydantic import BaseModel

from vaultspec_core.mcp_server.app import create_server
from vaultspec_core.mcp_server.envelope import _structured

from .conftest import EXPECTED_TOOLS

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]

#: How a generated reply fills an optional value. ``"null"`` sets every one to
#: ``None``. ``"nested"`` fills optional models, dataclasses and lists, so the
#: nulls inside them reach the wire, and sets optional scalars to ``None``.
_Fill = Literal["null", "nested"]

_SCALARS: dict[type, object] = {str: "x", int: 0, float: 0.0, bool: False}


def _is_container(annotation: Any) -> bool:
    """Return whether *annotation* is a model, a dataclass, or a list."""
    if typing.get_origin(annotation) in (list, tuple):
        return True
    if not isinstance(annotation, type):
        return False
    kind = cast("type[object]", annotation)
    return issubclass(kind, BaseModel) or dataclasses.is_dataclass(kind)


def _members(annotation: Any) -> tuple[Any, ...]:
    """Return a union's non-``None`` members, or *annotation* alone."""
    if typing.get_origin(annotation) in (typing.Union, types.UnionType):
        return tuple(
            arg for arg in typing.get_args(annotation) if arg is not type(None)
        )
    return (annotation,)


def _value(annotation: Any, fill: _Fill) -> Any:
    """Generate a value for *annotation* under *fill*."""
    if typing.get_origin(annotation) is typing.Annotated:
        return _value(typing.get_args(annotation)[0], fill)
    members = _members(annotation)
    nullable = typing.get_origin(annotation) in (
        typing.Union,
        types.UnionType,
    ) and type(None) in typing.get_args(annotation)
    if nullable and (fill == "null" or not _is_container(members[0])):
        return None
    return _concrete(members[0], fill)


def _concrete(annotation: Any, fill: _Fill) -> Any:
    """Generate a non-``None`` value for a non-union *annotation*."""
    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)
    if origin in (list, tuple):
        return [_value(args[0], fill)] if args else []
    if origin is dict:
        return {}
    if origin is Literal:
        return args[0]
    if annotation is Any or annotation is object:
        return "x"
    if isinstance(annotation, type) and issubclass(annotation, enum.Enum):
        return next(iter(annotation))
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return _model(annotation, fill)
    if isinstance(annotation, type) and dataclasses.is_dataclass(annotation):
        hints = typing.get_type_hints(annotation, include_extras=True)
        return annotation(
            **{
                field.name: _value(hints[field.name], fill)
                for field in dataclasses.fields(annotation)
            }
        )
    if annotation in _SCALARS:
        return _SCALARS[annotation]
    msg = f"no generator for result annotation {annotation!r}"
    raise TypeError(msg)


def _model(model: type[BaseModel], fill: _Fill) -> BaseModel:
    """Build *model* with every field generated from its annotation."""
    hints = typing.get_type_hints(model, include_extras=True)
    return model.model_validate(
        {name: _value(hints[name], fill) for name in model.model_fields}
    )


async def _tool_contracts(vault_root: Path) -> dict[str, tuple[Any, dict[str, Any]]]:
    """Map each tool to its declared result type and published output schema.

    The schema is the one ``tools/list`` sends, after every hook that leans
    it, since that is the schema a client validates a reply against.
    """
    _ = vault_root
    server = create_server()
    published = {
        tool.name: tool.output_schema
        for tool in await server.list_tools()
        if tool.output_schema is not None
    }
    return {
        tool.name: (tool.fn_metadata.output_model, published[tool.name])
        for tool in server._tool_manager.list_tools()
        if tool.name in published
    }


@pytest.mark.parametrize("fill", ["null", "nested"])
@pytest.mark.parametrize("name", sorted(EXPECTED_TOOLS))
async def test_a_null_filled_reply_validates_against_the_published_schema(
    vault_root: Path, name: str, fill: _Fill
) -> None:
    contracts = await _tool_contracts(vault_root)
    assert name in contracts, f"{name} publishes no output schema"
    output_model, schema = contracts[name]

    reply = _structured(_concrete(output_model, fill))

    validator = validator_for(schema)(schema)
    errors = [error.message for error in validator.iter_errors(reply)]
    assert not errors, f"{name} ({fill}) reply breaks its schema: {errors}"
