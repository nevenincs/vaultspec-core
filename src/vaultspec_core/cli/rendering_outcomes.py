"""Canonical outcome vocabulary and the ``--json`` envelope shape.

Split out of :mod:`.rendering`: the ``Outcome`` taxonomy, the per-item
:class:`OutcomeItem` shape, aggregation/counting helpers, the
``--json`` envelope builder (:func:`json_envelope`), and the shared
sync-outcome adapter (:func:`sync_outcomes`). Re-exported from
:mod:`.rendering` so no import site outside the package needs to change.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from vaultspec_core.cli.json_output import json_format_kwargs
from vaultspec_core.console import get_console

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from vaultspec_core.core.types import SyncResult


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
        print(json.dumps(envelope, **json_format_kwargs()))
    else:
        render_outcomes(items, title=title)
    return 1 if any(item.outcome is Outcome.FAILED for item in items) else 0


# Maps the per-file action strings recorded by ``sync_files`` onto the
# canonical outcome vocabulary, so a sync result renders through the same
# helper as every other state-changing surface.
_SYNC_ACTION_OUTCOME: dict[str, Outcome] = {
    "[ADD]": Outcome.CREATED,
    "[UPDATE]": Outcome.UPDATED,
    "[REFRESH]": Outcome.UPDATED,
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
