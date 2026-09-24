"""Tests for the hooks that lean a tool's published schemas.

``lean_tool_schema`` removes what validates nothing and tells the caller
nothing: derived titles, the default ``additionalProperties``, the null
branch of an omissible property, and the indirection of a definition used
once. The unit tests build real Pydantic schemas and check that every
constraint a caller acts on survives and that the leaned schema accepts what
the original accepted. The surface test reads the registered tools.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import TYPE_CHECKING, Annotated, Any

import pytest
from jsonschema.validators import validator_for
from pydantic import BaseModel, Field

from vaultspec_core.mcp_server.app import create_server
from vaultspec_core.mcp_server.envelope import LeanEnum, lean_tool_schema

from .conftest import vault_root

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["vault_root"]

pytestmark = [pytest.mark.unit]


class _Arguments(BaseModel):
    query: Annotated[str, Field(min_length=1, max_length=20)]
    title: str | None = None
    feature: Annotated[str | None, Field(description="Feature tag.")] = None
    limit: Annotated[int, Field(ge=1, le=9)] = 4
    options: dict[str, Any] | None = None
    anchor: str | None


class _Leaf(BaseModel):
    name: str


class _Pair(BaseModel):
    first: _Leaf
    second: _Leaf


class _Tree(BaseModel):
    label: str
    children: list[_Tree] = Field(default_factory=list)


class _Holder(BaseModel):
    pair: _Pair
    tree: _Tree


class _Kind(Enum):
    KEEP = "keep"
    REFUSED = "refused"
    ALSO = "also"


class _Filtered(BaseModel):
    kinds: list[Annotated[_Kind, LeanEnum({_Kind.KEEP, _Kind.ALSO})]]


def _accepts(schema: dict[str, Any], instance: dict[str, Any]) -> bool:
    return validator_for(schema)(schema).is_valid(instance)


def test_an_input_schema_keeps_its_constraints_and_loses_its_titles() -> None:
    lean = lean_tool_schema(_Arguments.model_json_schema())
    properties = lean["properties"]

    assert "title" not in lean
    assert properties["query"] == {"maxLength": 20, "minLength": 1, "type": "string"}
    assert properties["limit"] == {
        "default": 4,
        "maximum": 9,
        "minimum": 1,
        "type": "integer",
    }
    assert lean["required"] == ["query", "anchor"]
    # A property named ``title`` is a name, not the title keyword.
    assert properties["title"] == {"type": "string"}


def test_an_omissible_null_default_collapses_to_its_type() -> None:
    lean = lean_tool_schema(_Arguments.model_json_schema())["properties"]

    assert lean["feature"] == {"description": "Feature tag.", "type": "string"}
    # The default ``additionalProperties: true`` goes with the null branch.
    assert lean["options"] == {"type": "object"}


def test_a_required_nullable_keeps_its_null_branch() -> None:
    lean = lean_tool_schema(_Arguments.model_json_schema())["properties"]

    assert lean["anchor"] == {"anyOf": [{"type": "string"}, {"type": "null"}]}


def test_the_leaned_input_accepts_every_non_null_value_the_original_did() -> None:
    original = _Arguments.model_json_schema()
    lean = lean_tool_schema(original)
    instances: list[dict[str, Any]] = [
        {"query": "q", "anchor": None},
        {"query": "q", "anchor": "a", "feature": "f", "options": {"k": [1]}},
        {"query": "q", "anchor": "a", "title": "t", "limit": 9},
    ]
    refused: list[dict[str, Any]] = [
        {"query": "", "anchor": None},
        {"query": "q", "anchor": None, "limit": 10},
        {"anchor": None},
    ]

    for instance in instances:
        assert _accepts(original, instance)
        assert _accepts(lean, instance)
    for instance in refused:
        assert not _accepts(original, instance)
        assert not _accepts(lean, instance)


def test_a_definition_used_once_is_inlined_and_a_shared_one_stays() -> None:
    original = _Holder.model_json_schema()
    lean = lean_tool_schema(original)

    # _Leaf is referenced twice and _Tree refers to itself, so both stay.
    assert set(lean["$defs"]) == {"_Leaf", "_Tree"}
    pair = lean["properties"]["pair"]
    assert pair["properties"]["first"] == {"$ref": "#/$defs/_Leaf"}
    assert pair["required"] == ["first", "second"]
    assert lean["properties"]["tree"] == {"$ref": "#/$defs/_Tree"}
    assert len(json.dumps(lean)) < len(json.dumps(original))

    instance = {
        "pair": {"first": {"name": "a"}, "second": {"name": "b"}},
        "tree": {"label": "root", "children": [{"label": "leaf"}]},
    }
    assert _accepts(original, instance)
    assert _accepts(lean, instance)
    assert not _accepts(lean, {"pair": {"first": {}}, "tree": {"label": "x"}})


def test_a_schema_without_definitions_is_left_whole() -> None:
    lean = lean_tool_schema(_Leaf.model_json_schema())

    assert lean == {
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
        "type": "object",
    }


def test_a_filtered_enum_lists_only_the_members_it_names() -> None:
    items = _Filtered.model_json_schema()["properties"]["kinds"]["items"]

    assert items == {"enum": ["keep", "also"], "type": "string"}


def test_an_unfiltered_enum_lists_every_member() -> None:
    class _All(BaseModel):
        kind: Annotated[_Kind, LeanEnum()]

    kind = _All.model_json_schema()["properties"]["kind"]

    assert kind == {"enum": ["keep", "refused", "also"], "type": "string"}


@pytest.mark.parametrize("read_only", [False, True])
async def test_the_published_surface_carries_no_derived_titles_or_null_defaults(
    vault_root: Path, read_only: bool
) -> None:
    _ = vault_root
    for tool in await create_server(read_only=read_only).list_tools():
        for schema in (tool.input_schema, tool.output_schema or {}):
            wire = json.dumps(schema, separators=(",", ":"))
            # A ``title`` keyword holds a string; a property named ``title``
            # holds a schema object.
            assert '"title":"' not in wire, tool.name
            assert '"default":null' not in wire, tool.name
            assert '"additionalProperties":true' not in wire, tool.name
