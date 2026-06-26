"""CLI-layer rendering helpers for dry-run previews and sync summaries.

All Rich/console output for structured previews lives here, not in core.
Key exports: :func:`render_dry_run_tree` and the canonical outcome
vocabulary (:class:`Outcome`, :func:`render_outcomes`,
:func:`outcomes_as_json`). Depends on :mod:`vaultspec_core.core.dry_run`
for :class:`~vaultspec_core.core.dry_run.DryRunItem` and status styles;
consumed by :mod:`.root` and indirectly by :mod:`.vault_cmd`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from vaultspec_core.console import get_console

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from vaultspec_core.core.types import SyncResult
from vaultspec_core.core.dry_run import (
    STATUS_STYLE,
    DryRunItem,
    DryRunStatus,
    count_by_status,
    group_by_label,
)


class Outcome(StrEnum):
    """Canonical outcome-state vocabulary for state-changing operations.

    One word per terminal state of a state-changing CLI operation,
    shared across every sync-shaped surface (``install``, ``sync``, the
    ``spec * sync`` family, ``migrations run``, ``vault repair``,
    ``vault check ... --fix``) so operators and tooling read a single
    taxonomy instead of the five divergent vocabularies the CLI UX
    audit documented (findings S2, S8, S10). See the
    ``cli-sync-vocabulary`` ADR.

    Members:
        CREATED: A destination that did not exist now exists.
        UPDATED: A destination that existed was changed.
        UNCHANGED: Destination already matched source; no write happened.
        REMOVED: A destination that existed no longer does.
        RESTORED: A destination was reset to its canonical version.
        SKIPPED: A destination was not touched because a precondition
            or policy excluded it.
        FAILED: A write was attempted and an error was encountered.
        MIXED: Aggregate only - a single invocation produced items with
            more than one distinct outcome. Never assigned to an
            individual item.
    """

    CREATED = "created"
    UPDATED = "updated"
    UNCHANGED = "unchanged"
    REMOVED = "removed"
    RESTORED = "restored"
    SKIPPED = "skipped"
    FAILED = "failed"
    MIXED = "mixed"


# Glyph + Rich colour per outcome, for text rendering. The glyphs mirror
# the dry-run preview styling (+ create, ~ update, - removal) so a
# preview and the result of applying it read consistently.
OUTCOME_STYLE: dict[Outcome, tuple[str, str]] = {
    Outcome.CREATED: ("+", "green"),
    Outcome.UPDATED: ("~", "yellow"),
    Outcome.UNCHANGED: ("=", "dim"),
    Outcome.REMOVED: ("-", "red"),
    Outcome.RESTORED: ("*", "cyan"),
    Outcome.SKIPPED: ("s", "dim"),
    Outcome.FAILED: ("x", "bold red"),
    Outcome.MIXED: ("/", "magenta"),
}


@dataclass(frozen=True)
class OutcomeItem:
    """One named, classified result of a state-changing operation.

    Attributes:
        name: Identifier of the affected item - a resource name, a file
            path, a migration id; whatever the surface operates on.
        outcome: The canonical terminal state for this item. Never
            :attr:`Outcome.MIXED` (that value is reserved for
            aggregates).
        detail: Optional human-readable annotation. Carries domain-
            specific colour a single outcome word cannot - a skip
            reason, or a plan-revision operation name such as
            "renumbered" - without fragmenting the taxonomy.
        group: Optional grouping label. When set, the text renderer
            collects the item under a sub-heading (e.g. one provider per
            group on ``sync``); an empty string renders at the root.
    """

    name: str
    outcome: Outcome
    detail: str = ""
    group: str = ""


def aggregate_outcome(items: Sequence[OutcomeItem]) -> Outcome:
    """Collapse per-item outcomes into one summary outcome.

    Returns the shared outcome when every item agrees,
    :attr:`Outcome.MIXED` when they disagree, and
    :attr:`Outcome.UNCHANGED` for an empty set - nothing happened,
    which is the honest summary of a no-op run.

    Args:
        items: The per-item outcomes of a single invocation.

    Returns:
        The single summary :class:`Outcome` for the invocation. This is
        the value a ``--json`` envelope's top-level ``status`` field
        carries.
    """
    distinct = {item.outcome for item in items}
    if not distinct:
        return Outcome.UNCHANGED
    if len(distinct) == 1:
        return next(iter(distinct))
    return Outcome.MIXED


def count_outcomes(items: Sequence[OutcomeItem]) -> dict[Outcome, int]:
    """Return per-outcome occurrence counts for an invocation's items."""
    counts: dict[Outcome, int] = {}
    for item in items:
        counts[item.outcome] = counts.get(item.outcome, 0) + 1
    return counts


def outcomes_as_json(items: Sequence[OutcomeItem]) -> dict[str, object]:
    """Build the machine-readable payload for a set of outcomes.

    The single source of truth for the ``--json`` representation of a
    state-changing operation: the top-level ``status`` is the aggregate
    outcome, ``items`` is the per-item breakdown. Text rendering
    (:func:`render_outcomes`) and this function consume the same
    :class:`OutcomeItem` list, so the two surfaces cannot drift apart.

    Args:
        items: The per-item outcomes of a single invocation.

    Returns:
        A JSON-serialisable mapping with ``status`` (the aggregate
        outcome word) and ``items`` (the per-item records).
    """
    return {
        "status": str(aggregate_outcome(items)),
        "items": [
            {
                "name": item.name,
                "outcome": str(item.outcome),
                **({"group": item.group} if item.group else {}),
                **({"detail": item.detail} if item.detail else {}),
            }
            for item in items
        ],
    }


def _outcome_line(item: OutcomeItem, *, indent: str) -> str:
    """Format one glyph-prefixed outcome line at the given indent."""
    glyph, colour = OUTCOME_STYLE[item.outcome]
    detail = f" [dim]{item.detail}[/dim]" if item.detail else ""
    return f"{indent}[{colour}]{glyph}[/{colour}] {item.name}{detail}"


def render_outcomes(items: Sequence[OutcomeItem], *, title: str = "Result") -> None:
    """Print a human-readable outcome summary to the console.

    Renders one glyph-prefixed line per item that represents an actual
    change, followed by a per-outcome count summary. :attr:`Outcome.
    UNCHANGED` items are folded into the count summary only and never
    listed line by line - a result that reports every untouched file is
    noise. The machine-readable surface (:func:`outcomes_as_json`) keeps
    full per-item fidelity, so the JSON still carries every record.

    When any item carries a :attr:`OutcomeItem.group`, the items are
    collected under one sub-heading per group; a group whose every item
    is unchanged collapses to a single ``up to date`` acknowledgement so
    a no-op multi-target run stays compact.

    Consumes the same :class:`OutcomeItem` list as
    :func:`outcomes_as_json`; the text and JSON surfaces therefore share
    one taxonomy and one aggregate and cannot drift apart.

    Args:
        items: The per-item outcomes of a single invocation.
        title: Heading printed above the per-item lines.
    """
    console = get_console()
    console.print(f"[bold]{title}[/bold]")

    if any(item.group for item in items):
        grouped: dict[str, list[OutcomeItem]] = {}
        for item in items:
            grouped.setdefault(item.group, []).append(item)
        for group, members in grouped.items():
            label = group or "(ungrouped)"
            changed = [m for m in members if m.outcome is not Outcome.UNCHANGED]
            if changed:
                console.print(f"  [bold dim]{label}[/bold dim]")
                for member in changed:
                    console.print(_outcome_line(member, indent="    "))
            else:
                console.print(f"  [dim]= {label}  up to date[/dim]")
    else:
        for item in items:
            if item.outcome is Outcome.UNCHANGED:
                continue
            console.print(_outcome_line(item, indent="  "))

    counts = count_outcomes(items)
    parts: list[str] = []
    for outcome in Outcome:
        n = counts.get(outcome, 0)
        if n:
            _, colour = OUTCOME_STYLE[outcome]
            parts.append(f"[{colour}]{n} {outcome.value}[/{colour}]")
    if parts:
        console.print("  " + "  ".join(parts))


def json_envelope(
    command: str,
    status: str,
    data: Mapping[str, object],
    *,
    version: int = 1,
    hints: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Wrap a command payload in the canonical ``--json`` envelope.

    Per the ``cli-json-consistency`` ADR every ``--json`` output shares
    one shape - ``{schema, status, data, hints}`` - so a CI consumer
    matches a single pattern across every verb.

    Args:
        command: Dotted command identifier (e.g. ``"sync"``,
            ``"spec.rules.sync"``); forms the ``schema`` string.
        status: The invocation's aggregate canonical outcome word.
        data: The command's own payload, nested unmodified.
        version: Schema version suffix appended to the ``schema`` string
            (e.g. ``1`` yields ``vaultspec.{command}.v1``). Defaults to
            ``1``; all existing callers inherit ``v1`` unchanged. Pass
            ``version=2`` when a command's payload shape has been bumped
            and the consuming contract must be versioned (e.g.
            :func:`cmd_graph` after the v2 envelope bump).
        hints: Optional structured next-step hint; omitted when absent.

    Returns:
        The envelope mapping ``{schema, status, data}`` plus ``hints``
        when supplied.

    Example::

        # Default v1 - all existing callers unchanged
        json_envelope("vault.check", "unchanged", {...})
        # => {"schema": "vaultspec.vault.check.v1", ...}

        # Explicit v2 for the graph command after its schema bump
        json_envelope("vault.graph", "unchanged", {...}, version=2)
        # => {"schema": "vaultspec.vault.graph.v2", ...}
    """
    envelope: dict[str, object] = {
        "schema": f"vaultspec.{command}.v{version}",
        "status": str(status),
        "data": dict(data),
    }
    if hints is not None:
        envelope["hints"] = dict(hints)
    return envelope


def emit_outcomes(
    items: Sequence[OutcomeItem],
    *,
    command: str,
    title: str,
    json_output: bool,
    extra_json: Mapping[str, object] | None = None,
    hints: Mapping[str, object] | None = None,
) -> int:
    """Emit a set of outcomes as text or JSON and return the exit code.

    The shared exit point for every sync-shaped command. With
    ``json_output`` it prints the canonical ``status``/``items`` envelope
    (merged with any ``extra_json``); otherwise it prints the
    human-readable summary. Returns ``1`` when any item is
    :attr:`Outcome.FAILED`, else ``0`` - a failed outcome is the one
    outcome that stops a pipeline. The caller raises :class:`typer.Exit`
    with the returned code.

    Args:
        items: The per-item outcomes of a single invocation.
        command: Dotted command identifier for the JSON ``schema`` field.
        title: Heading for the text rendering.
        json_output: When true, emit the JSON envelope instead of text.
        extra_json: Optional extra keys merged into the envelope's
            ``data`` payload (e.g. ``warnings``). Ignored for text output.
        hints: Optional structured next-step hint; omitted when absent.

    Returns:
        The process exit code: ``1`` if any outcome failed, else ``0``.
    """
    if json_output:
        import json

        inner = outcomes_as_json(items)
        data: dict[str, object] = {"items": inner["items"]}
        if extra_json:
            data.update(extra_json)
        envelope = json_envelope(command, str(inner["status"]), data, hints=hints)
        print(json.dumps(envelope, indent=2))
    else:
        render_outcomes(items, title=title)
    return 1 if any(item.outcome is Outcome.FAILED for item in items) else 0


# Maps the per-file action strings recorded by ``sync_files`` onto the
# canonical outcome vocabulary, so a sync result renders through the same
# helper as every other state-changing surface.
_SYNC_ACTION_OUTCOME: dict[str, Outcome] = {
    "[ADD]": Outcome.CREATED,
    "[UPDATE]": Outcome.UPDATED,
    "[UNCHANGED]": Outcome.UNCHANGED,
    "[DELETE]": Outcome.REMOVED,
    "[SKIP]": Outcome.SKIPPED,
}


def sync_outcomes(result: SyncResult, *, group: str = "") -> list[OutcomeItem]:
    """Translate a :class:`~vaultspec_core.core.types.SyncResult` into outcomes.

    Maps the per-file action log onto the canonical taxonomy and appends
    one :attr:`Outcome.FAILED` item per recorded error. The returned list
    is what both :func:`render_outcomes` and :func:`outcomes_as_json`
    consume, so a sync surface's text and JSON cannot drift apart.

    Args:
        result: The accumulator returned by a sync pass.
        group: Optional grouping label stamped onto every returned item -
            used by multi-target callers (e.g. ``sync`` tagging each
            provider) so the renderer can sub-head the output.

    Returns:
        One :class:`OutcomeItem` per file the sync pass touched or
        inspected, in pass order, with errors appended last.
    """
    items = [
        OutcomeItem(
            name=path,
            outcome=_SYNC_ACTION_OUTCOME.get(action, Outcome.UPDATED),
            group=group,
        )
        for path, action in result.items
    ]
    for error in result.errors:
        name, _, detail = error.partition(": ")
        items.append(
            OutcomeItem(name=name, outcome=Outcome.FAILED, detail=detail, group=group)
        )
    return items


# =============================================================================
# The output contract: Record, Listing, and box-free Tree shapes.
#
# Per the cli-output-standardization ADR, every read surface renders through one
# of these shapes instead of a Rich ``Table``/``Panel``/``Tree``. Each shape is a
# payload object with a text renderer and a JSON renderer that consume the same
# object, mirroring how :class:`OutcomeItem` feeds both :func:`render_outcomes`
# and :func:`outcomes_as_json`. The text rules: a header at column 0, items at a
# two-space indent, single-space fields in a stable order whose names equal the
# JSON keys, one terminating summary line, an explicit one-line empty state, no
# box-drawing characters, and no width-dependent layout. Colour, when present,
# decorates a value only and is redundant with the text, so a piped or
# ``NO_COLOR`` run loses nothing.
# =============================================================================

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
    :func:`emit_outcomes` this returns no exit code: a read surface owns its own
    exit semantics (e.g. a status command exiting non-zero on drift) and calls
    :class:`typer.Exit` itself.

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


def render_install_summary(
    source_counts: dict[str, int],
    *,
    path: str,
    providers: Sequence[str],
    has_mcp: bool = False,
) -> None:
    """Render a concise post-install summary.

    Shows what was found in the vaultspec source (the actual number of
    rules, skills, and agents the user authored) and which providers
    they were synced to.

    Args:
        source_counts: Mapping of resource type to count, e.g.
            ``{"rules": 1, "skills": 2, "agents": 9}``.
        path: Display path of the installation target.
        providers: Provider names that were enabled (e.g. ``["claude"]``).
        has_mcp: Whether the MCP server configuration was installed.
    """
    console = get_console()

    # --- Header (box-free per the output contract) ---
    console.print()
    console.print("[bold green]Installed[/bold green] vaultspec")
    console.print(f"  [dim]Target[/dim] {path}")

    # --- Source resource counts ---
    category_order = ["rules", "skills", "agents"]
    summary_parts: list[str] = []
    for cat in category_order:
        n = source_counts.get(cat, 0)
        if n:
            label = cat if n != 1 else cat.rstrip("s")
            summary_parts.append(f"[bold]{n}[/bold] {label}")

    if summary_parts:
        console.print(f"  Synced {', '.join(summary_parts)}")

    # --- Providers ---
    if providers:
        provider_list = ", ".join(f"[cyan]{p}[/cyan]" for p in providers)
        console.print(f"  Enabled {provider_list}")

    # --- MCP ---
    if has_mcp:
        console.print("  Installed [cyan]MCP server[/cyan]")

    console.print()


def render_sharing_policy() -> None:
    """Print the spec-layer sharing-policy statement.

    Per the cli-spec-gitignore ADR, install and upgrade state the
    team-shared default plainly so an operator knows authored content
    reaches teammates and only runtime by-products stay local.
    """
    console = get_console()
    console.print("[bold]Sharing policy[/bold]")
    console.print(
        "  [dim].vaultspec/[/dim] (rules, skills, agents, system), "
        "[dim]CLAUDE.md[/dim], and [dim].mcp.json[/dim] are committed to git "
        "so teammates inherit your project policy."
    )
    console.print(
        "  Runtime by-products ([dim].vaultspec/_snapshots/[/dim], lock "
        "files, [dim]providers.json[/dim]) stay local."
    )
    console.print()


def render_uninstall_summary(
    removed: Sequence[tuple[str, str]], *, path: str, keep_vault: bool = True
) -> None:
    """Render a concise post-uninstall summary.

    Args:
        removed: ``(path, label)`` tuples for removed items.
        path: Display path of the uninstall target.
        keep_vault: Whether ``.vault/`` was preserved.
    """
    console = get_console()

    # Extract provider names from labels
    known_providers = {"claude", "gemini", "antigravity", "codex"}
    providers: list[str] = []
    seen: set[str] = set()
    for _, label in removed:
        name = label.split("(")[0].strip().lower() if "(" in label else label.lower()
        if name in known_providers and name not in seen:
            seen.add(name)
            providers.append(name)

    # Header (box-free per the output contract).
    console.print()
    console.print("[bold red]Uninstalled[/bold red] vaultspec")
    console.print(f"  [dim]Target[/dim] {path}")

    if providers:
        provider_list = ", ".join(f"[cyan]{p}[/cyan]" for p in providers)
        console.print(f"  Disabled {provider_list}")

    if keep_vault:
        console.print(
            "  [dim].vault/ preserved"
            "  - pass --remove-vault to also remove documentation[/dim]"
        )


_NEXT_STEP_HINTS: dict[tuple[str, str], tuple[str, str]] = {
    ("vault.add.research", "created"): (
        "vaultspec-core vault add adr --feature {feature} --related {research_stem}",
        "Define an Architecture Decision Record (ADR) for your research",
    ),
    ("vault.add.adr", "created"): (
        "vaultspec-core vault add plan --feature {feature} --related {adr_stem}",
        "Draft an implementation plan based on your ADR",
    ),
    ("vault.add.plan", "created"): (
        "vaultspec-core vault add exec --all-steps --feature {feature} "
        "--related {plan_stem}",
        "Scaffold step-aware execution records for your plan",
    ),
    ("vault.add.exec", "created"): (
        "vaultspec-core vault plan status",
        "Track the progress and verification of your plan",
    ),
    ("vault.add.audit", "created"): (
        "vaultspec-core vault rule promote --from {audit_stem} --as {rule_name}",
        "Promote your audit findings to a team-shared rule",
    ),
    ("vault.check.all", "unchanged"): (
        'git commit -m "Commit changes after successful vault checks"',
        "Your vault is clean. Proceed to commit your changes",
    ),
    ("vault.check.all", "failed"): (
        "vaultspec-core vault repair",
        "Run safe auto-corrections to resolve vault errors",
    ),
    ("install", "created"): (
        "vaultspec-core vault add research --feature {feature_tag}",
        "Framework installed. Start research on your first feature",
    ),
    ("install", "updated"): (
        "vaultspec-core vault add research --feature {feature_tag}",
        "Framework updated. Start research on your first feature",
    ),
    ("vault.feature.archive", "updated"): (
        "vaultspec-core vault check all",
        "Verify your vault remains completely clean after archiving",
    ),
    ("vault.feature.rename", "updated"): (
        "vaultspec-core vault check all",
        "Verify your vault is completely clean after renaming the feature",
    ),
}


class SafeDict(dict):
    """A dictionary that retains unknown string placeholders for formatting."""

    def __missing__(self, key: str) -> str:
        return f"{{{key}}}"


def hints_suppressed(no_hints: bool = False) -> bool:
    """Report whether next-step hints are suppressed for this invocation.

    Hints are advisory and must be silenceable for scripted contexts, per
    the cli-next-step-hints ADR. They are off when the caller passes
    ``--no-hints`` or the ``VAULTSPEC_NO_HINTS=1`` environment variable is
    set. This is the one predicate every hint surface consults so the
    suppression contract cannot drift per command.
    """
    import os

    return no_hints or os.environ.get("VAULTSPEC_NO_HINTS") == "1"


def render_next_actions(pairs: Sequence[tuple[str, str]]) -> None:
    """Print next-step hints in the one uniform footer form.

    Per the cli-presentation-uniformity ADR every next-step hint, from
    every command, renders identically: a ``Next action:`` header (or
    ``Next actions:`` for more than one) at column 0, then each hint as a
    two-space-indented description with its command indented a further two
    spaces. This mirrors the plain footer of ``vaultspec-rag`` and
    replaces the divergent ``Suggested Next Step:`` forms.

    Args:
        pairs: ``(description, command)`` hints in display order. An empty
            sequence prints nothing.
    """
    from rich.markup import escape

    items = list(pairs)
    if not items:
        return
    console = get_console()
    console.print()
    header = "Next action:" if len(items) == 1 else "Next actions:"
    console.print(f"[bold]{header}[/bold]")
    for description, command in items:
        console.print(f"  {escape(description)}")
        console.print(f"    [cyan]{escape(command)}[/cyan]")


def emit_next_step_hint(
    command: str,
    outcome: str,
    context_vars: dict[str, str] | None = None,
    json_output: bool = False,
    no_hints: bool = False,
) -> dict[str, object] | None:
    """Emit the next-step advisory hint for a command and outcome.

    Checks the VAULTSPEC_NO_HINTS environment variable and the --no-hints
    flag suppression.

    Returns:
        A dict matching {"text": str, "command": str} for JSON, or None.
        Also prints to the console if not json_output.
    """
    if hints_suppressed(no_hints):
        return None

    hint = _NEXT_STEP_HINTS.get((command, outcome))
    if not hint:
        return None

    cmd_template, description = hint
    # Format safely using SafeDict so missing variables remain placeholders
    safe_vars = SafeDict(context_vars or {})
    formatted_command = cmd_template.format_map(safe_vars)

    if not json_output:
        render_next_actions([(description, formatted_command)])

    return {"text": description, "command": formatted_command}


# ---------------------------------------------------------------------------
# Clean plan-line rendering
# ---------------------------------------------------------------------------


def plan_line_cells(
    *,
    name: str,
    tier: str | None,
    waves_completed: int,
    wave_count: int,
    phases_completed: int,
    phase_count: int,
    steps_completed: int,
    step_count: int,
    completion_percent: float,
    next_open_step: str | None,
    exec_missing: int = 0,
) -> list[str]:
    """Return the column cells of one clean plan-overview line.

    The line is deliberately glyph-free and label-light so it reads the
    same everywhere it appears - the rollup's in-flight and recently-
    completed rows and the targeted-trace header. Containers the tier does
    not use render as ``-`` (no Waves at L1/L2; no Phases at L1). The
    cursor cell names the next open step, or ``complete`` when none remain.
    A non-zero *exec_missing* count renders a trailing ``!n`` flag so a
    checked-but-ungrounded plan is visible at a glance.

    Returns a fixed eight-cell row so a column of rows aligns under
    :func:`align_plan_rows`.
    """
    waves = f"W{waves_completed}/{wave_count}" if wave_count else "-"
    phases = f"P{phases_completed}/{phase_count}" if phase_count else "-"
    cursor = f"next {next_open_step}" if next_open_step else "complete"
    flag = f"!{exec_missing}" if exec_missing else ""
    return [
        name,
        tier or "-",
        waves,
        phases,
        f"{steps_completed}/{step_count} steps",
        f"{completion_percent:g}%",
        cursor,
        flag,
    ]


def align_plan_rows(rows: Sequence[Sequence[str]], *, gap: str = "   ") -> list[str]:
    """Left-pad cells column-wise so a set of plan rows aligns cleanly.

    Each row is padded to the per-column maximum width and joined with
    *gap*; trailing whitespace (from empty cells such as an absent
    ``!n`` flag) is stripped so lines never carry dangling spaces.
    """
    if not rows:
        return []
    width = max(len(row) for row in rows)
    col_widths = [
        max(len(row[i]) if i < len(row) else 0 for row in rows) for i in range(width)
    ]
    lines: list[str] = []
    for row in rows:
        padded = [
            (row[i] if i < len(row) else "").ljust(col_widths[i]) for i in range(width)
        ]
        lines.append(gap.join(padded).rstrip())
    return lines


def active_feature_tail(
    *,
    tier: str | None,
    steps_completed: int,
    step_count: int,
    completion_percent: float,
) -> str:
    """Return the condensed plan tail for an active-features row.

    Shorter than the full plan line: just ``<tier> <k>/<N> <p>%``. Empty
    string when the feature has no plan (``step_count`` is zero), so the
    row stays clean for plan-less features.
    """
    if not step_count:
        return ""
    return f"{tier or '-'} {steps_completed}/{step_count} {completion_percent:g}%"
