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
        hints: Optional structured next-step hint; omitted when absent.

    Returns:
        The envelope mapping ``{schema, status, data}`` plus ``hints``
        when supplied.
    """
    envelope: dict[str, object] = {
        "schema": f"vaultspec.{command}.v1",
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

    Returns:
        The process exit code: ``1`` if any outcome failed, else ``0``.
    """
    if json_output:
        import json

        inner = outcomes_as_json(items)
        data: dict[str, object] = {"items": inner["items"]}
        if extra_json:
            data.update(extra_json)
        envelope = json_envelope(command, str(inner["status"]), data)
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


def render_dry_run_tree(items: Sequence[DryRunItem], *, title: str = "Preview") -> None:
    """Render a coloured Rich tree of dry-run items to the console.

    Items with a non-empty ``label`` are grouped under a sub-tree branch;
    unlabelled items appear at the root level.  A summary line with
    per-status counts is printed after the tree.

    Status colour coding: ``+`` green (new), ``=`` dim (no change),
    ``~`` yellow (update), ``!`` bold yellow (override), ``-`` red (delete).

    Args:
        items: Sequence of :class:`~vaultspec_core.core.dry_run.DryRunItem`
            to render.
        title: Title displayed at the root node of the tree.
    """
    from rich.tree import Tree

    console = get_console()
    tree = Tree(f"[bold]{title}[/bold]")

    for label, group in group_by_label(list(items)).items():
        branch = tree.add(f"[bold dim]{label}[/bold dim]") if label else tree

        for item in group:
            prefix, colour = STATUS_STYLE[item.status]
            branch.add(f"[{colour}]{prefix} {item.path}[/{colour}]")

    console.print(tree)

    # Summary line
    by_status = count_by_status(list(items))
    parts = []
    for status in DryRunStatus:
        count = by_status.get(status, 0)
        if count:
            prefix, colour = STATUS_STYLE[status]
            parts.append(f"[{colour}]{prefix} {count} {status.value}[/{colour}]")
    if parts:
        console.print("  ".join(parts))


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
    from rich.panel import Panel

    console = get_console()

    # --- Header ---
    console.print()
    console.print(
        Panel(
            f"[bold green]Installed[/bold green]  vaultspec\n"
            f"[dim]Target[/dim]     {path}",
            expand=False,
            border_style="green",
        )
    )

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
    from rich.panel import Panel

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

    console.print()
    console.print(
        Panel(
            f"[bold red]Uninstalled[/bold red]  vaultspec\n"
            f"[dim]Target[/dim]       {path}",
            expand=False,
            border_style="red",
        )
    )

    if providers:
        provider_list = ", ".join(f"[cyan]{p}[/cyan]" for p in providers)
        console.print(f"  Disabled {provider_list}")

    if keep_vault:
        console.print(
            "  [dim].vault/ preserved"
            "  - pass --remove-vault to also remove documentation[/dim]"
        )
