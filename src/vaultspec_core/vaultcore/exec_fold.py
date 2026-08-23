"""Plan the fold of per-Step execution records into one ledger per plan.

A ``body-v1`` execution record carries its Step identity in frontmatter and
its machine-usable content in a ``## Scope`` list the scaffolder filled from
the originating Step row. Everything else in the body is prose that no
consumer reads.

Folding recovers exactly that machine-usable content: each record's Scope
paths become ledger rows under the record's Step id. The operation is
**not** invented. ``body-v1`` never recorded whether a path was added,
modified, or deleted, so a recovered row carries
:data:`~vaultspec_core.vaultcore.exec_ledger.MIGRATED_OP` (``T``, touched),
which a reader can always distinguish from an operation an executor
actually reported.

The prose is discarded. That is the point of the fold, and it is bounded
rather than irreversible: ``.vault/`` is tracked, so the commit preceding a
fold retains every discarded body.

This module only *plans*. It reads nothing and writes nothing; the caller
supplies parsed records and applies the returned plan. Keeping the decision
pure is what lets a dry run and a real run share one code path, so what an
operator previews is what an operator gets.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .exec_ledger import LEDGER_SUFFIX, MIGRATED_OP, format_row

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from pathlib import Path

__all__ = [
    "FoldPlan",
    "FoldSource",
    "SkippedRecord",
    "plan_fold",
    "scope_paths",
]

#: A backtick-quoted cell inside a ``## Scope`` list item.
_CELL_RE = re.compile(r"`([^`]*)`")

#: The ``## Scope`` section, up to the next level-two heading.
_SCOPE_RE = re.compile(
    r"^##[ \t]+Scope[ \t]*$(?P<body>.*?)(?=^##[ \t]+|\Z)",
    re.MULTILINE | re.DOTALL,
)

#: A canonical leaf Step identifier, used to order rows numerically.
_STEP_NUM_RE = re.compile(r"^S(\d+)$")


@dataclass(frozen=True)
class FoldSource:
    """One parsed execution record offered to the planner.

    Attributes:
        path: The record's path.
        step_id: Its ``step_id`` frontmatter value, or ``None``.
        body: Its body text, frontmatter already stripped.
    """

    path: Path
    step_id: str | None
    body: str


@dataclass(frozen=True)
class SkippedRecord:
    """One record the planner declined to fold, and why."""

    path: Path
    reason: str


@dataclass
class FoldPlan:
    """The decided outcome of folding one plan's execution records.

    Attributes:
        rows: Ledger rows to append, in Step order.
        folded: Records whose content the rows now carry, safe to remove.
        skipped: Records left untouched, each with a reason.
        recovered_paths: Count of distinct scope paths carried into rows.
    """

    rows: list[str] = field(default_factory=list)
    folded: list[Path] = field(default_factory=list)
    skipped: list[SkippedRecord] = field(default_factory=list)
    recovered_paths: int = 0

    @property
    def is_empty(self) -> bool:
        """Whether the plan would fold nothing."""
        return not self.folded


def scope_paths(body: str) -> tuple[str, ...]:
    """Return the backticked paths listed in *body*'s ``## Scope`` section.

    Args:
        body: The record body, frontmatter already stripped.

    Returns:
        The scope paths in document order, deduplicated, with empty cells
        dropped. Empty when the record declares no Scope section or the
        section lists no backticked cell.
    """
    match = _SCOPE_RE.search(body)
    if match is None:
        return ()
    seen: dict[str, None] = {}
    for cell in _CELL_RE.findall(match.group("body")):
        value = cell.strip()
        if value:
            seen.setdefault(value, None)
    return tuple(seen)


def _step_sort_key(step_id: str) -> tuple[int, str]:
    """Order Step ids numerically, keeping unparseable ids last but stable."""
    match = _STEP_NUM_RE.match(step_id)
    if match:
        return (int(match.group(1)), "")
    return (10**9, step_id)


def plan_fold(sources: Iterable[FoldSource]) -> FoldPlan:
    """Decide which records fold into a ledger, and what rows they become.

    A record is skipped rather than folded when folding it would lose
    something the ledger cannot carry:

    - the ledger itself, which is the fold's target, not its input;
    - a Phase summary, which rolls up Steps rather than documenting one and
      has no Step id to key a row on;
    - a record with no ``step_id``, which cannot be attributed to a Step at
      all, so folding it would silently drop its evidence.

    A record with a Step id but no Scope paths still folds: it contributes a
    path-less row so the Step stays mapped to a real artifact. Losing that
    row would make a previously recorded Step read as never executed.

    Args:
        sources: The candidate records.

    Returns:
        The decided :class:`FoldPlan`.
    """
    plan = FoldPlan()
    foldable: list[tuple[str, Path, tuple[str, ...]]] = []

    for source in sources:
        stem = source.path.stem
        if stem.endswith(LEDGER_SUFFIX):
            plan.skipped.append(SkippedRecord(source.path, "is the ledger"))
            continue
        if stem.endswith("-summary"):
            plan.skipped.append(SkippedRecord(source.path, "phase summary"))
            continue
        if not source.step_id:
            plan.skipped.append(SkippedRecord(source.path, "no step_id"))
            continue
        foldable.append((source.step_id, source.path, scope_paths(source.body)))

    foldable.sort(key=lambda item: (_step_sort_key(item[0]), item[1].name))

    for step_id, path, paths in foldable:
        if paths:
            plan.rows.extend(format_row(step_id, MIGRATED_OP, p) for p in paths)
            plan.recovered_paths += len(paths)
        else:
            # Coverage-only row: the Step was executed and recorded, but the
            # record named no path. Dropping it would lose the mapping.
            plan.rows.append(format_row(step_id, MIGRATED_OP))
        plan.folded.append(path)

    return plan


def summarize(plan: FoldPlan, folder: str) -> str:
    """Render a one-line operator summary of *plan* for *folder*."""
    return (
        f"{folder}: {len(plan.folded)} record(s) -> "
        f"{len(plan.rows)} row(s), {plan.recovered_paths} path(s) recovered, "
        f"{len(plan.skipped)} skipped"
    )


def sources_from(
    records: Sequence[tuple[Path, str | None, str]],
) -> tuple[FoldSource, ...]:
    """Build planner inputs from ``(path, step_id, body)`` triples."""
    return tuple(FoldSource(path, step_id, body) for path, step_id, body in records)
