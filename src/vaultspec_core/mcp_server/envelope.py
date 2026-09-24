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
from typing import TYPE_CHECKING, Any, ParamSpec, Protocol, TypeVar, cast, override

from mcp.types import CallToolResult, TextContent
from pydantic import BaseModel, GetJsonSchemaHandler, TypeAdapter

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Collection
    from enum import Enum

__all__ = [
    "LeanEnum",
    "LeanModel",
    "LeanResult",
    "LeanShape",
    "compact_result",
    "describe",
    "lean_tool_schema",
    "tool_description",
]

_P = ParamSpec("_P")
_R = TypeVar("_R")

#: Hard cap on the summary line.  A summary that grows with the payload would
#: reintroduce the defect this module exists to remove, so the cap is on the
#: rendered string rather than on the caller's good intentions.
_MAX_SUMMARY_CHARS = 200
_JSON_ADAPTER: TypeAdapter[Any] = TypeAdapter(Any)


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

#: Matches the ``ctx`` entry inside an ``Args:`` block: its line and every
#: continuation line indented deeper than it, stopping at the next argument.
#:
#: ``ctx`` is the MCP request context: a parameter of the Python function that
#: appears in no ``inputSchema``, so documenting it describes an argument the
#: model cannot pass. Two tools spend a full sentence explaining it is unused.
#: The entry is found by indentation relative to its own line, not by a fixed
#: width: ``inspect.getdoc`` dedents the docstring, so a fixed width read the
#: next argument as a continuation and removed every argument after ``ctx``.
_CTX_ARG = re.compile(r"\n(?P<indent>[ \t]*)ctx:[^\n]*(?:\n(?P=indent)[ \t]+[^\n]*)*")

#: An ``Args:`` heading left with nothing under it after the ctx removal.
_EMPTY_ARGS = re.compile(r"\n\s*Args:\s*(?=\Z)")

#: A reST inline literal. The model reads Markdown, where one backtick marks
#: code; the doubled reST form costs two characters a literal and means the
#: same thing.
_REST_LITERAL = re.compile(r"``([^`]+)``")


def tool_description(fn: object) -> str:
    """Return *fn*'s docstring trimmed to what the model can act on.

    The summary and the per-parameter guidance survive; the sections that
    duplicate the schema or describe machinery the caller never touches do
    not. reST literals render as Markdown ones, and each argument as one
    unindented line. Applied at registration, so the docstring stays intact
    in source for whoever maintains the function.

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
    doc = _REST_LITERAL.sub(r"`\1`", doc)
    return _flatten_indents(doc).strip()


def _flatten_indents(doc: str) -> str:
    """Render each indented entry of *doc* as one unindented line.

    A docstring indents an ``Args:`` entry under its heading and its wrapped
    lines under the entry. The indentation is layout for a fixed-width reader:
    every wrapped line spends eight spaces saying it continues the line above,
    which a line break already says. Entries keep a line each; their wrapped
    lines join them. Unindented prose is untouched.

    Args:
        doc: A dedented docstring.

    Returns:
        The docstring with indentation removed and wrapped entries joined.
    """
    lines: list[str] = []
    entry_indent: int | None = None
    for line in doc.split("\n"):
        text = line.lstrip()
        indent = len(line) - len(text)
        if not indent or not text:
            entry_indent = None
            lines.append(line)
        elif entry_indent is None or indent <= entry_indent:
            entry_indent = indent
            lines.append(text)
        else:
            lines[-1] = f"{lines[-1]} {text}"
    return "\n".join(lines)


class LeanModel(BaseModel):
    """Result-model base that keeps maintainer documentation off the wire.

    Pydantic lifts a model's ``__doc__`` into its JSON-schema ``description``,
    so a Google-style docstring - ``Attributes:`` block and reST markup
    included - is re-sent to the model on every turn of every conversation.
    Measured, output schemas were 26,785 of 43,919 characters of the tool
    surface, and not one of those descriptions sat on a leaf field: each
    described its fields in prose the model then had to re-associate by name.
    Maximum bytes, least usable position.

    Derived ``title`` keys go for the same reason: Pydantic title-cases the
    property name, so ``blob_hash`` yields ``Blob Hash`` - 1,892 characters
    across the surface carrying nothing the key does not already say.

    What survives is what a caller acts on: the structure, and any
    ``Field(description=...)`` an author wrote deliberately for the model. The
    docstrings stay in the source, where the maintainer needs them.
    """

    @override
    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: Any, handler: GetJsonSchemaHandler
    ) -> dict[str, Any]:
        """Render this model's schema without its class docstring or titles.

        Args:
            core_schema: The pydantic-core schema for this model.
            handler: The next handler in the generation chain.

        Returns:
            The pruned schema fragment.
        """
        produced = dict(handler(core_schema))
        _lean_object(produced)
        return produced


class LeanResult(LeanModel):
    """Base for a model that is only ever a tool's result, never its input.

    A property default describes what a caller may leave out of a request,
    and a result is never a request: the wire either carries the key or, for
    an optional key, omits it. So a result model's schema drops every
    property default, as :class:`LeanShape` does for a dataclass. An input
    model keeps :class:`LeanModel`, whose defaults tell the caller what it
    may omit.

    For the same reason an optional key's schema drops its ``null`` branch:
    :func:`compact_result` omits an optional key rather than sending it null,
    so the branch describes a value the wire never carries. A required key
    that may be null keeps ``null``, spelled as a type list where the other
    branch is a plain type.
    """

    @override
    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: Any, handler: GetJsonSchemaHandler
    ) -> dict[str, Any]:
        """Render this model's schema lean and without property defaults.

        Args:
            core_schema: The pydantic-core schema for this model.
            handler: The next handler in the generation chain.

        Returns:
            The pruned schema fragment.
        """
        produced = super().__get_pydantic_json_schema__(core_schema, handler)
        properties = cast("dict[str, Any]", produced.get("properties", {}))
        required = cast("list[str]", produced.get("required", []))
        for name, prop in properties.items():
            prop.pop("default", None)
            properties[name] = _collapse_nullable(prop, omissible=name not in required)
        return produced


class LeanEnum:
    """``Annotated`` marker that ships an enum as its values alone.

    :class:`LeanModel` cannot reach an enum: Pydantic renders one as a shared
    ``$defs`` entry carrying the enum class's docstring and a derived title,
    and the reference to it costs bytes of its own. The values are what a
    caller can act on, so annotating a field ``Annotated[SomeEnum,
    LeanEnum()]`` inlines ``{"enum": [...], "type": "string"}`` in place; the
    unreferenced definition is then dropped from the schema. Validation and
    serialisation are untouched - only the schema changes.

    A field that accepts only some of the enum's members names them, and the
    schema lists those alone: a value the tool always refuses is not one a
    caller can act on.
    """

    __slots__ = ("_values",)

    def __init__(self, members: Collection[Enum] | None = None) -> None:
        """Mark an enum field, optionally listing only *members*.

        Args:
            members: The members the field accepts; ``None`` lists them all.
        """
        self._values = None if members is None else {m.value for m in members}

    def __get_pydantic_json_schema__(
        self, core_schema: Any, handler: GetJsonSchemaHandler
    ) -> dict[str, Any]:
        """Render the enum inline, without its docstring or title.

        Args:
            core_schema: The pydantic-core schema for the enum.
            handler: The next handler in the generation chain.

        Returns:
            The enum's schema fragment, inlined.
        """
        produced = handler.resolve_ref_schema(handler(core_schema))
        lean = {
            key: value
            for key, value in produced.items()
            if key not in ("description", "title")
        }
        if self._values is not None:
            values = cast("list[Any]", lean["enum"])
            lean["enum"] = [value for value in values if value in self._values]
        return lean


class LeanShape:
    """``Annotated`` marker that ships a domain dataclass as a result shape.

    A field typed from the dataclass a service already returns needs no
    result-model copy of it, but Pydantic renders a dataclass the way it
    renders a model: with its docstring and derived titles. This marker prunes
    them as :class:`LeanModel` does, keeping the shared ``$defs`` entry so a
    shape used twice is described once.

    Every property is also marked required and loses its default: a dataclass
    serialises every field, so a default describes input the wire never takes.
    An enum-typed field is inlined as its values, as :class:`LeanEnum` would
    ship it: the dataclass's own annotation cannot carry that marker.
    """

    def __get_pydantic_json_schema__(
        self, core_schema: Any, handler: GetJsonSchemaHandler
    ) -> dict[str, Any]:
        """Prune the dataclass's shared definition in place.

        Args:
            core_schema: The pydantic-core schema for the dataclass.
            handler: The next handler in the generation chain.

        Returns:
            The reference to the pruned definition.
        """
        reference = handler(core_schema)
        definition = handler.resolve_ref_schema(reference)
        _lean_object(definition)
        properties = cast("dict[str, Any]", definition.get("properties", {}))
        for name, prop in properties.items():
            prop.pop("default", None)
            inlined = _inline_enums(prop, handler)
            properties[name] = _collapse_nullable(inlined, omissible=False)
        definition["required"] = list(properties)
        return reference


def _inline_enums(node: Any, handler: GetJsonSchemaHandler) -> Any:
    """Replace each reference to an enum definition with the enum's values.

    Args:
        node: A property's schema fragment.
        handler: The handler that resolves the fragment's references.

    Returns:
        The fragment with every enum inlined as ``enum`` and ``type`` alone.
    """
    if isinstance(node, list):
        return [_inline_enums(item, handler) for item in cast("list[Any]", node)]
    if not isinstance(node, dict):
        return node
    fragment = cast("dict[str, Any]", node)
    if "$ref" in fragment:
        target = handler.resolve_ref_schema(fragment)
        if "enum" in target:
            return {key: target[key] for key in ("enum", "type") if key in target}
        return fragment
    return {key: _inline_enums(value, handler) for key, value in fragment.items()}


def _lean_object(schema: dict[str, Any]) -> None:
    """Drop an object schema's description and every derived title, in place.

    Args:
        schema: An object schema fragment.
    """
    schema.pop("description", None)
    schema.pop("title", None)
    properties = schema.get("properties")
    if isinstance(properties, dict):
        schema["properties"] = {
            name: _strip_titles(prop)
            for name, prop in cast("dict[str, Any]", properties).items()
        }


#: Keywords of a nullable property's one non-null branch that may be hoisted
#: beside a ``["T", "null"]`` type: each constrains only instances of its own
#: type, so a null still validates. ``enum`` is handled apart, because it
#: constrains every instance and must list ``null`` itself.
_HOISTABLE = frozenset({"type", "enum", "items", "additionalProperties"})

#: The null branch Pydantic pairs with an optional field's own schema.
_NULL_BRANCH: dict[str, Any] = {"type": "null"}


def _collapse_nullable(node: Any, *, omissible: bool) -> Any:
    """Shorten a result property's ``anyOf`` of one schema and ``null``.

    Pydantic renders ``str | None`` as ``{"anyOf": [{"type": "string"},
    {"type": "null"}]}``. An omissible key never travels as null, so its
    fragment becomes the non-null branch alone. A required key keeps null as
    ``{"type": ["string", "null"]}``, which validates the same instances in
    about half the characters; a branch that is a reference, or that carries
    a keyword outside :data:`_HOISTABLE`, keeps its union.

    Args:
        node: A property's schema fragment.
        omissible: Whether the key is omitted, rather than sent null, when
            it has no value.

    Returns:
        The fragment, shortened when its union is a nullable schema.
    """
    if not isinstance(node, dict):
        return node
    fragment = cast("dict[str, Any]", node)
    branches = fragment.get("anyOf")
    if not isinstance(branches, list) or len(cast("list[Any]", branches)) != 2:
        return fragment
    value, null = cast("list[Any]", branches)
    if null != _NULL_BRANCH or not isinstance(value, dict):
        return fragment
    branch = cast("dict[str, Any]", value)
    collapsed = {key: item for key, item in fragment.items() if key != "anyOf"}
    if omissible:
        return {**collapsed, **branch}
    if not isinstance(branch.get("type"), str) or not branch.keys() <= _HOISTABLE:
        return fragment
    collapsed.update(branch)
    collapsed["type"] = [branch["type"], "null"]
    if "enum" in branch:
        collapsed["enum"] = [*branch["enum"], None]
    return collapsed


#: Keywords whose value maps names to subschemas. A key inside one of these
#: maps is a property or definition name, never a keyword, so a property
#: named ``title`` survives the title stripping.
_SCHEMA_MAPS = frozenset(
    {"properties", "patternProperties", "$defs", "definitions", "dependentSchemas"}
)

#: Keywords whose value is a single subschema.
_SCHEMA_VALUES = frozenset(
    {
        "items",
        "additionalProperties",
        "not",
        "contains",
        "propertyNames",
        "if",
        "then",
        "else",
        "unevaluatedItems",
        "unevaluatedProperties",
    }
)

#: Keywords whose value is a list of subschemas.
_SCHEMA_LISTS = frozenset({"anyOf", "allOf", "oneOf", "prefixItems"})

#: The prefix of a reference into the schema's own ``$defs``.
_LOCAL_DEFS = "#/$defs/"


def _map_subschemas(
    schema: dict[str, Any], transform: Callable[[Any], Any]
) -> dict[str, Any]:
    """Return *schema* with *transform* applied to each immediate subschema.

    Only keyword positions that hold schemas are visited: an ``enum`` or
    ``default`` value is data, and a ``properties`` key is a name.

    Args:
        schema: A schema object.
        transform: Applied to every direct subschema.

    Returns:
        A new schema object; *schema* is not modified.
    """
    mapped: dict[str, Any] = {}
    for key, value in schema.items():
        if key in _SCHEMA_MAPS and isinstance(value, dict):
            named = cast("dict[str, Any]", value)
            mapped[key] = {name: transform(sub) for name, sub in named.items()}
        elif key in _SCHEMA_VALUES and isinstance(value, dict):
            mapped[key] = transform(value)
        elif key in _SCHEMA_LISTS and isinstance(value, list):
            mapped[key] = [transform(sub) for sub in cast("list[Any]", value)]
        else:
            mapped[key] = value
    return mapped


def _strip_titles(node: Any) -> Any:
    """Drop derived ``title`` keywords from a schema fragment and its subschemas.

    Args:
        node: A schema fragment.

    Returns:
        The fragment without derived titles.
    """
    if not isinstance(node, dict):
        return node
    stripped = _map_subschemas(cast("dict[str, Any]", node), _strip_titles)
    stripped.pop("title", None)
    return stripped


def lean_tool_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Return a tool's input or output schema without what carries no meaning.

    The models a tool declares are leaned where Pydantic renders them, but
    the SDK wraps them in schemas of its own - the arguments object built
    from the function signature, and the wrapper around a ``list`` result -
    that no model hook reaches. This is applied to the whole published
    schema instead, and removes only what validates nothing and tells the
    caller nothing:

    * derived ``title`` keywords, such as ``"Query"`` for ``query`` and
      ``"searchArguments"`` for the arguments object;
    * ``"additionalProperties": true``, which is the JSON Schema default;
    * the ``null`` branch and ``null`` default of a property absent from
      ``required``, as :class:`LeanResult` drops them from a result: leaving
      the key out already says the value is optional, and a non-null default
      is kept because it tells the caller what omission means;
    * a ``$defs`` entry referenced once, which is inlined where it is used.
      An entry shared by two properties stays shared, so the schema never
      grows.

    Every value the schema accepted before, other than an explicit ``null``
    for an omissible key, it accepts after.

    Args:
        schema: A tool's published input or output schema.

    Returns:
        The leaned schema; *schema* is not modified.
    """
    return _inline_single_use(_lean_node(schema))


def _lean_node(node: Any) -> Any:
    """Lean one schema object and its subschemas; see :func:`lean_tool_schema`.

    Args:
        node: A schema fragment.

    Returns:
        The leaned fragment.
    """
    if not isinstance(node, dict):
        return node
    lean = _map_subschemas(cast("dict[str, Any]", node), _lean_node)
    lean.pop("title", None)
    if lean.get("additionalProperties") is True:
        del lean["additionalProperties"]
    properties = lean.get("properties")
    if isinstance(properties, dict):
        required = set(cast("list[str]", lean.get("required", [])))
        lean["properties"] = {
            name: prop if name in required else _without_null_default(prop)
            for name, prop in cast("dict[str, Any]", properties).items()
        }
    return lean


def _without_null_default(prop: Any) -> Any:
    """Collapse an omissible property whose default is ``null``.

    Args:
        prop: The schema of a property absent from ``required``.

    Returns:
        The non-null branch alone when the property is a nullable union
        defaulting to ``null``; otherwise *prop* unchanged.
    """
    if not isinstance(prop, dict):
        return prop
    fragment = cast("dict[str, Any]", prop)
    if "default" not in fragment or fragment["default"] is not None:
        return fragment
    bare = {key: value for key, value in fragment.items() if key != "default"}
    collapsed = _collapse_nullable(bare, omissible=True)
    return fragment if collapsed is bare else collapsed


def _local_refs(node: Any) -> list[str]:
    """Return the ``$defs`` names every reference in *node* points at.

    Args:
        node: A schema fragment.

    Returns:
        One name per reference, repeated as often as it is referenced.
    """
    if not isinstance(node, dict):
        return []
    fragment = cast("dict[str, Any]", node)
    names: list[str] = []
    ref = fragment.get("$ref")
    if isinstance(ref, str) and ref.startswith(_LOCAL_DEFS):
        names.append(ref.removeprefix(_LOCAL_DEFS))

    def collect(sub: Any) -> Any:
        names.extend(_local_refs(sub))
        return sub

    _map_subschemas(fragment, collect)
    return names


def _inline_single_use(schema: dict[str, Any]) -> dict[str, Any]:
    """Inline every ``$defs`` entry that exactly one reference points at.

    A shared definition earns its place when two references reuse it. With
    one, the definition and its reference cost the name twice plus the
    reference syntax, and the reader resolves an indirection for nothing.
    A definition reached recursively, or referenced more than once, stays.

    Args:
        schema: A whole schema, carrying its ``$defs`` at the root.

    Returns:
        The schema with single-use definitions inlined and unreferenced ones
        dropped.
    """
    definitions = schema.get("$defs")
    if not isinstance(definitions, dict) or not definitions:
        return schema
    defs = cast("dict[str, Any]", definitions)
    counts: dict[str, int] = {}
    for name in _local_refs(schema):
        counts[name] = counts.get(name, 0) + 1

    def expand(node: Any, active: frozenset[str]) -> Any:
        if not isinstance(node, dict):
            return node
        fragment = cast("dict[str, Any]", node)
        ref = fragment.get("$ref")
        if isinstance(ref, str) and ref.startswith(_LOCAL_DEFS):
            name = ref.removeprefix(_LOCAL_DEFS)
            if counts.get(name) == 1 and name in defs and name not in active:
                siblings = {key: v for key, v in fragment.items() if key != "$ref"}
                body = expand(defs[name], active | {name})
                return {
                    **body,
                    **_map_subschemas(siblings, lambda s: expand(s, active)),
                }
        return _map_subschemas(fragment, lambda sub: expand(sub, active))

    root = expand({k: v for k, v in schema.items() if k != "$defs"}, frozenset())
    kept: dict[str, Any] = {}
    pending = _local_refs(root)
    while pending:
        name = pending.pop()
        if name in kept or name not in defs:
            continue
        kept[name] = expand(defs[name], frozenset({name}))
        pending.extend(_local_refs(kept[name]))
    if not kept:
        return root
    return {"$defs": dict(sorted(kept.items())), **root}


def _prune_optional_nulls(model: BaseModel, dumped: dict[str, Any]) -> dict[str, Any]:
    """Drop ``None`` values whose field is optional, keeping required ones.

    A field that is absent and a field that is present-and-null read the same
    to a caller against an optional schema, and the second costs bytes on every
    row: ``find`` returns a sixteen-field superset covering two modes, so
    twelve fields were null on every feature row.

    Blanket ``exclude_none`` is wrong here. A field can be *required* and
    nullable - ``next_open_step`` is declared ``str | None`` with no default,
    so dropping it produced a payload that failed its own output-schema
    validation on the way back out. Required fields keep their nulls; only
    fields the schema already treats as omissible are pruned.

    Args:
        model: The result model the dump came from.
        dumped: Its JSON-mode dump.

    Returns:
        The dump with optional nulls removed.
    """
    optional = {
        name
        for name, field in type(model).model_fields.items()
        if not field.is_required()
    }
    return {
        key: value
        for key, value in dumped.items()
        if value is not None or key not in optional
    }


def _prune_any(value: Any) -> Any:
    """Recursively prune optional nulls from *value*.

    Args:
        value: A model, a sequence, a mapping, or a scalar.

    Returns:
        The value with optional nulls removed from every nested model.
    """
    if isinstance(value, BaseModel):
        dumped = value.model_dump(mode="json", by_alias=True)
        pruned = _prune_optional_nulls(value, dumped)
        return {
            key: _prune_any(getattr(value, key, item)) for key, item in pruned.items()
        }
    if isinstance(value, list | tuple):
        return [_prune_any(item) for item in cast("list[Any]", value)]
    return _JSON_ADAPTER.dump_python(value, mode="json", by_alias=True)


def _structured(payload: object) -> Any:
    """Render *payload* the way the SDK would for ``structured_content``.

    Optional nulls are pruned; see :func:`_prune_optional_nulls`.

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
        return _prune_any(payload)
    return {"result": _prune_any(payload)}


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
