"""Parse the consolidated execution ledger's mechanical ``## Changes`` rows.

A plan may record its execution either as one document per Step (the
per-Step record) or as a single append-only ledger naming every Step it
covers. Both carry the same ``## Changes`` body contract; they differ only
in whether a row leads with a Step identifier:

    - `M` `src/module.py`            <- per-Step record (step is the document)
    - `S01` `M` `src/module.py`      <- ledger row (step is the column)

Consolidating removes the per-Step scaffold tax without losing per-Step
addressability: the identity the plan's Step ids provide moves from the
filename into the row, so a Step still maps to a real artifact and a reader
can still trace one Step's implementation.

This module is the single parser for those rows. Both the shared
``ExecRecordIndex`` and the ``exec-mapping`` check resolve a ledger's Step
coverage through it, so the two never drift.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = [
    "LEDGER_SUFFIX",
    "LedgerRow",
    "append_rows",
    "format_row",
    "is_ledger_stem",
    "ledger_step_ids",
    "parse_ledger_rows",
]

#: Filename-stem suffix marking a consolidated ledger, mirroring the
#: ``-summary`` convention already used to select the summary contract.
LEDGER_SUFFIX = "-ledger"

#: A canonical leaf Step identifier (``S1``, ``S01``, ``S109``).
_STEP_RE = re.compile(r"^S\d{1,4}$")

#: The change operations a row may declare.
_OPS = frozenset({"A", "M", "D", "R"})

#: One list row, captured before its backticked cells are split out.
_ROW_RE = re.compile(r"^[ \t]*[-*][ \t]+(?P<cells>.+?)[ \t]*$")

#: A backtick-quoted cell.
_CELL_RE = re.compile(r"`([^`]*)`")

#: The ``## Changes`` section, up to the next level-two heading.
_CHANGES_RE = re.compile(
    r"^##[ \t]+Changes[ \t]*$(?P<body>.*?)(?=^##[ \t]+|\Z)",
    re.MULTILINE | re.DOTALL,
)


@dataclass(frozen=True)
class LedgerRow:
    """One parsed ``## Changes`` row.

    Attributes:
        step_id: The row's leading Step identifier, or ``None`` for a
            per-Step record's row (where the document supplies the Step).
        op: The change operation (``A``, ``M``, ``D``, ``R``), or ``None``
            for a non-change row such as a ``verify:`` line.
        paths: The backticked paths the row names, in row order. A rename
            carries two; a ``verify:`` row carries none.
    """

    step_id: str | None
    op: str | None
    paths: tuple[str, ...]


def is_ledger_stem(stem: str) -> bool:
    """Return whether a document stem names a consolidated ledger."""
    return stem.endswith(LEDGER_SUFFIX)


def _changes_body(body: str) -> str | None:
    """Return the raw ``## Changes`` section text, or ``None`` when absent."""
    match = _CHANGES_RE.search(body)
    return match.group("body") if match else None


def parse_ledger_rows(body: str) -> tuple[LedgerRow, ...]:
    """Parse every ``## Changes`` row in *body*.

    Rows outside ``## Changes`` are ignored, so a ``## Notes`` section's
    prose can never be mistaken for a change row. A row that parses into no
    backticked cells is skipped rather than raising: a malformed row is a
    check's finding to report, not this parser's to crash on (No-Crash
    policy).

    Args:
        body: The document body, frontmatter already stripped.

    Returns:
        The parsed rows in document order.
    """
    section = _changes_body(body)
    if section is None:
        return ()

    rows: list[LedgerRow] = []
    for line in section.splitlines():
        row_match = _ROW_RE.match(line)
        if row_match is None:
            continue
        cells = _CELL_RE.findall(row_match.group("cells"))
        if not cells:
            continue

        index = 0
        step_id: str | None = None
        if _STEP_RE.match(cells[index]):
            step_id = cells[index]
            index += 1

        op: str | None = None
        if index < len(cells) and cells[index] in _OPS:
            op = cells[index]
            index += 1

        rows.append(LedgerRow(step_id=step_id, op=op, paths=tuple(cells[index:])))
    return tuple(rows)


def ledger_step_ids(body: str) -> tuple[str, ...]:
    """Return every distinct Step id a ledger body covers, in first-seen order.

    Args:
        body: The ledger document body, frontmatter already stripped.

    Returns:
        The Step identifiers, deduplicated and ordered by first appearance.
        Empty when the body declares no ``## Changes`` rows carrying a Step
        id, which a caller should treat as an unlinked record rather than an
        error.
    """
    seen: dict[str, None] = {}
    for row in parse_ledger_rows(body):
        if row.step_id is not None:
            seen.setdefault(row.step_id, None)
    return tuple(seen)


def format_row(step_id: str, op: str, *paths: str) -> str:
    """Render one mechanical ``## Changes`` row.

    Args:
        step_id: The Step the row belongs to (e.g. ``S01``).
        op: The change operation (``A``, ``M``, ``D``, ``R``), or
            ``verify:`` for a check line.
        *paths: The paths (or, for a check line, the command and result).

    Returns:
        The row text, without a trailing newline.
    """
    cells = " -> ".join(f"`{path}`" for path in paths)
    return f"- `{step_id}` `{op}`{' ' + cells if cells else ''}"


def append_rows(body: str, rows: Sequence[str]) -> str:
    """Return *body* with *rows* appended to its ``## Changes`` section.

    The ledger is append-only: existing rows are never reordered or
    rewritten, and rows land at the end of ``## Changes`` rather than at the
    end of the document, so a trailing ``## Notes`` section stays intact and
    its prose is never parsed as coverage.

    A row already present verbatim in the section is not appended again, so
    re-running a Step is idempotent rather than duplicating its log.

    Args:
        body: The document body, frontmatter already stripped.
        rows: The rendered rows to append.

    Returns:
        The updated body.

    Raises:
        ValueError: If *body* declares no ``## Changes`` section, which means
            the document is not a ledger and appending would invent one.
    """
    match = _CHANGES_RE.search(body)
    if match is None:
        message = "document has no '## Changes' section to append to"
        raise ValueError(message)

    section = match.group("body")
    existing = {line.strip() for line in section.splitlines() if line.strip()}
    fresh = [row for row in rows if row.strip() not in existing]
    if not fresh:
        return body

    # Rebuild the section with exactly one blank line before the appended
    # rows and one after, so repeated appends cannot accumulate whitespace.
    kept = section.rstrip("\n")
    if not kept.endswith("\n") and kept:
        kept += "\n"
    updated = f"{kept}{chr(10).join(fresh)}\n\n"
    return body[: match.start("body")] + updated + body[match.end("body") :]
