"""The output contract: Record, Listing, and box-free Tree shapes.

Split out of :mod:`.rendering`. Per the cli-output-standardization ADR,
every read surface renders through one of these shapes instead of a
Rich ``Table``/``Panel``/``Tree``. Each shape is a payload object with a
text renderer and a JSON renderer that consume the same object,
mirroring how :class:`~.rendering_outcomes.OutcomeItem` feeds both
``render_outcomes`` and ``outcomes_as_json``. The text rules: a header
at column 0, items at a two-space indent, single-space fields in a
stable order whose names equal the JSON keys, one terminating summary
line, an explicit one-line empty state, no box-drawing characters, and
no width-dependent layout. Colour, when present, decorates a value only
and is redundant with the text, so a piped or ``NO_COLOR`` run loses
nothing. Re-exported from :mod:`.rendering` so no import site outside
the package needs to change.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from vaultspec_core.cli.rendering_outcomes import json_envelope
from vaultspec_core.console import get_console
from vaultspec_core.core.dry_run import (
    STATUS_STYLE,
    DryRunStatus,
    count_by_status,
    group_by_label,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from vaultspec_core.core.dry_run import DryRunItem

# Fixed truncation marker. ASCII so it survives a cp1252 stdout unchanged.
TRUNCATE_MARKER = "..."


def truncate(text: str, budget: int) -> str:
    """Truncate ``text`` to a fixed character ``budget`` with an explicit marker.

    The budget is a constant supplied by the caller, never derived from
    :attr:`Console.width`, so the elision point does not depend on the terminal.
    A value within budget is returned unchanged; a longer value is cut and
    suffixed with :data:`TRUNCATE_MARKER` so a reader knows it was elided and can
    fetch the full value from ``--json``.

    Args:
        text: The value to bound.
        budget: Maximum rendered length including the marker.

    Returns:
        The original text, or a marked truncation no longer than ``budget``.
    """
    if len(text) <= budget:
        return text
    if budget <= len(TRUNCATE_MARKER):
        return TRUNCATE_MARKER[:budget]
    return text[: budget - len(TRUNCATE_MARKER)] + TRUNCATE_MARKER


def summary_line(
    total: int, noun: str, breakdown: Sequence[tuple[int, str]] | None = None
) -> str:
    """Build a shape's terminating summary string.

    The summary gives a reader the aggregate the renderer already knew, so the
    model never reconstructs a total by counting lines. Zero-count breakdown
    entries are dropped so the parenthetical carries signal only.

    Args:
        total: The item count.
        noun: The already-correct noun for the count (e.g. ``"rules"``); the
            caller owns singular/plural so this helper makes no English guesses.
        breakdown: Optional ``(count, label)`` pairs rendered as a parenthetical,
            e.g. ``[(2, "project"), (1, "builtin")]`` -> ``" (2 project, 1
            builtin)"``.

    Returns:
        A single line such as ``"3 rules (2 project, 1 builtin)"``.
    """
    line = f"{total} {noun}"
    if breakdown:
        inner = ", ".join(f"{n} {label}" for n, label in breakdown if n)
        if inner:
            line += f" ({inner})"
    return line


@dataclass(frozen=True)
class Field:
    """One ``key: value`` pair in a :class:`Record`.

    Attributes:
        key: The field name. Equals the key this field carries in the JSON
            payload, so the text and machine surfaces name fields identically.
        value: The rendered value text.
        style: Optional Rich colour for the value on the human surface only.
            Never load-bearing: any state encoded here is also present in
            ``value`` or ``key`` so a colour-stripped read loses nothing.
    """

    key: str
    value: str
    style: str = ""


def render_record(fields: Sequence[Field], *, title: str) -> None:
    """Print a single entity's fields as ``key: value`` lines.

    Header at column 0, fields at a two-space indent in the given (stable) order.
    No box-drawing and no width padding; the line is built as a plain string and
    handed to the console, not laid out by a table engine. Dynamic text is
    escaped so a value containing Rich markup characters cannot break rendering.

    Args:
        fields: The entity's fields, in canonical display order.
        title: Heading printed above the fields.
    """
    from rich.markup import escape

    console = get_console()
    console.print(f"[bold]{escape(title)}[/bold]")
    for field in fields:
        value = escape(field.value)
        if field.style:
            value = f"[{field.style}]{value}[/{field.style}]"
        console.print(f"  {escape(field.key)}: {value}")


def record_as_json(fields: Sequence[Field]) -> dict[str, str]:
    """Return the ``{key: value}`` payload for a record; decorative styles drop."""
    return {field.key: field.value for field in fields}


def emit_record(
    fields: Sequence[Field],
    *,
    command: str,
    title: str,
    json_output: bool,
    status: str = "unchanged",
    extra_json: Mapping[str, object] | None = None,
    hints: Mapping[str, object] | None = None,
) -> None:
    """Emit a record as text or as the canonical JSON envelope.

    The shared exit point for field/value surfaces. The text and JSON forms
    consume the same :class:`Field` list, so they cannot drift. Unlike
    :func:`~.rendering_outcomes.emit_outcomes` this returns no exit code: a
    read surface owns its own exit semantics (e.g. a status command exiting
    non-zero on drift) and calls :class:`typer.Exit` itself.

    Args:
        fields: The entity's fields.
        command: Dotted command identifier for the JSON ``schema`` field.
        title: Heading for the text rendering.
        json_output: When true, emit the JSON envelope instead of text.
        status: The envelope's aggregate ``status`` word. Defaults to
            ``"unchanged"`` - the honest status of a read.
        extra_json: Optional extra keys merged into the envelope ``data``.
        hints: Optional structured next-step hint.
    """
    if json_output:
        import json

        data: dict[str, object] = dict(record_as_json(fields))
        if extra_json:
            data.update(extra_json)
        print(json.dumps(json_envelope(command, status, data, hints=hints), indent=2))
    else:
        render_record(fields, title=title)


@dataclass(frozen=True)
class Cell:
    """One value in a :class:`Listing` row, with optional decorative colour.

    Attributes:
        text: The rendered value.
        style: Optional Rich colour for the human surface only; never
            load-bearing (see :class:`Field`).
    """

    text: str
    style: str = ""


@dataclass(frozen=True)
class Column:
    """A :class:`Listing` column: a JSON key and the field's identity.

    A listing carries no rendered column header - the column key names the field
    in the JSON payload only. Text rows render values single-space separated in
    column order, so the key never appears in the text surface.

    Attributes:
        key: The JSON key and the row-mapping lookup key for this column.
    """

    key: str


def _as_cell(value: object) -> Cell:
    """Coerce a row value into a :class:`Cell`, leaving an existing one as-is."""
    if isinstance(value, Cell):
        return value
    return Cell(value if isinstance(value, str) else str(value))


def render_listing(
    rows: Sequence[Mapping[str, object]],
    columns: Sequence[Column],
    *,
    title: str,
    summary: str | None = None,
    empty: str = "none",
) -> None:
    """Print a flat listing: one space-separated row per item, then a summary.

    Header at column 0, rows at a two-space indent, values single-space separated
    in column order with no width padding. An empty listing collapses to one
    explicit line rather than an empty frame. Dynamic text is escaped so a value
    containing Rich markup cannot break rendering.

    Args:
        rows: One mapping per item; each maps a column key to a ``str`` or a
            :class:`Cell`. A missing key renders empty.
        columns: The columns in display (and JSON) order.
        title: Heading printed above the rows.
        summary: Optional terminating summary line (see :func:`summary_line`).
        empty: The one-line body printed when ``rows`` is empty.
    """
    from rich.markup import escape

    console = get_console()
    console.print(f"[bold]{escape(title)}[/bold]")
    if not rows:
        console.print(f"  [dim]{escape(empty)}[/dim]")
        return
    for row in rows:
        parts: list[str] = []
        for column in columns:
            cell = _as_cell(row.get(column.key, ""))
            text = escape(cell.text)
            if cell.style:
                text = f"[{cell.style}]{text}[/{cell.style}]"
            parts.append(text)
        console.print("  " + " ".join(parts))
    if summary:
        console.print(f"  [dim]{escape(summary)}[/dim]")


def listing_as_json(
    rows: Sequence[Mapping[str, object]], columns: Sequence[Column]
) -> list[dict[str, str]]:
    """Return the per-row ``{key: value}`` payload for a listing (styles drop)."""
    return [
        {column.key: _as_cell(row.get(column.key, "")).text for column in columns}
        for row in rows
    ]


def emit_listing(
    rows: Sequence[Mapping[str, object]],
    columns: Sequence[Column],
    *,
    command: str,
    title: str,
    json_output: bool,
    summary: str | None = None,
    empty: str = "none",
    status: str = "unchanged",
    extra_json: Mapping[str, object] | None = None,
    hints: Mapping[str, object] | None = None,
) -> None:
    """Emit a listing as text or as the canonical JSON envelope.

    The shared exit point for multi-row surfaces. The text and JSON forms consume
    the same rows and columns, so they cannot drift. The JSON ``data`` carries
    ``items`` (the full per-row payload with no truncation).

    Args:
        rows: One mapping per item (see :func:`render_listing`).
        columns: The columns in display and JSON order.
        command: Dotted command identifier for the JSON ``schema`` field.
        title: Heading for the text rendering.
        json_output: When true, emit the JSON envelope instead of text.
        summary: Optional terminating summary line for the text surface.
        empty: One-line body for an empty text listing.
        status: The envelope's aggregate ``status`` word.
        extra_json: Optional extra keys merged into the envelope ``data``.
        hints: Optional structured next-step hint.
    """
    if json_output:
        import json

        data: dict[str, object] = {"items": listing_as_json(rows, columns)}
        if extra_json:
            data.update(extra_json)
        print(json.dumps(json_envelope(command, status, data, hints=hints), indent=2))
    else:
        render_listing(rows, columns, title=title, summary=summary, empty=empty)


@dataclass(frozen=True)
class TreeLine:
    """One node in a box-free :func:`render_tree` rendering.

    Hierarchy is conveyed by ``depth`` (two spaces per level) and an optional
    ASCII status glyph, never by connector glyphs such as the box-drawing set a
    Rich ``Tree`` emits.

    Attributes:
        text: The node label.
        depth: Nesting depth; the root level is ``0``.
        glyph: Optional one-character ASCII status marker (``+ ~ - = *``) shown
            before the label, reusing the dry-run / outcome glyph vocabulary.
        style: Optional decorative Rich colour for the line; never load-bearing.
    """

    text: str
    depth: int = 0
    glyph: str = ""
    style: str = ""


def render_tree(lines: Sequence[TreeLine], *, title: str) -> None:
    """Print a hierarchy as indentation, with no connector characters.

    Each level adds two spaces; an optional ASCII glyph precedes the label. The
    line is built as a plain string and escaped, so no box-drawing glyph is ever
    emitted and a value containing Rich markup cannot break rendering.

    Args:
        lines: The nodes in pre-order, each carrying its own ``depth``.
        title: Heading printed at column 0 above the tree.
    """
    from rich.markup import escape

    console = get_console()
    console.print(f"[bold]{escape(title)}[/bold]")
    for line in lines:
        indent = "  " * (line.depth + 1)
        body = f"{line.glyph} {escape(line.text)}" if line.glyph else escape(line.text)
        if line.style:
            body = f"[{line.style}]{body}[/{line.style}]"
        console.print(f"{indent}{body}")


def render_dry_run_tree(items: Sequence[DryRunItem], *, title: str = "Preview") -> None:
    """Render dry-run items as a box-free indentation tree to the console.

    Items with a non-empty ``label`` are grouped one indentation level under a
    sub-heading; unlabelled items appear at the root level. A summary line with
    per-status counts follows. Built on :func:`render_tree`, so hierarchy is
    indentation only - never box-drawing connector glyphs.

    Status glyph coding: ``+`` green (new), ``=`` dim (no change),
    ``~`` yellow (update), ``!`` bold yellow (override), ``-`` red (delete).

    Args:
        items: Sequence of :class:`~vaultspec_core.core.dry_run.DryRunItem`
            to render.
        title: Heading displayed at column 0 above the tree.
    """
    lines: list[TreeLine] = []
    for label, group in group_by_label(list(items)).items():
        depth = 0
        if label:
            lines.append(TreeLine(label, depth=0, style="bold dim"))
            depth = 1
        for item in group:
            prefix, colour = STATUS_STYLE[item.status]
            lines.append(TreeLine(item.path, depth=depth, glyph=prefix, style=colour))
    render_tree(lines, title=title)

    # Summary line
    by_status = count_by_status(list(items))
    parts = []
    for status in DryRunStatus:
        count = by_status.get(status, 0)
        if count:
            prefix, colour = STATUS_STYLE[status]
            parts.append(f"[{colour}]{prefix} {count} {status.value}[/{colour}]")
    if parts:
        get_console().print("  " + "  ".join(parts))
