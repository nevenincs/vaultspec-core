"""Parse and append the execution ledger's mechanical rows.

A plan records its execution in one append-only ledger per plan. Every row
in its ``## Changes`` section leads with the Step it belongs to:

    - `S01` `M` `src/module.py`               <- a change row (A, M, D, R, T)
    - `S01` `verify:` `pytest` -> `pass`      <- a check row
    - `S01` `by:` `vaultspec-high-executor`   <- an attribution row

A ``## Notes`` section, present only on exception, carries one
``- `S##` text`` line per note. Only ``## Changes`` rows register a Step as
covered, so a note can never make a Step read as executed.

A per-Step record from before the ledger carried the same ``## Changes``
contract without the Step column (the document supplied the Step); the
parser still reads that shape so the fold migration can recover it.

This module is the single parser for those rows. The shared
``ExecRecordIndex``, the ``exec-mapping`` check, and the fold all resolve
a ledger through it, so they cannot drift.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = [
    "BY_LABEL",
    "LEDGER_SUFFIX",
    "MIGRATED_OP",
    "VERIFY_LABEL",
    "LedgerRow",
    "StepEvidence",
    "append_notes",
    "append_rows",
    "format_note",
    "format_row",
    "is_ledger_stem",
    "ledger_step_evidence",
    "ledger_step_ids",
    "note_lines",
    "parse_ledger_rows",
]

#: Filename-stem suffix marking a ledger.
LEDGER_SUFFIX = "-ledger"

#: A canonical leaf Step identifier (``S1``, ``S01``, ``S109``).
_STEP_RE = re.compile(r"^S\d{1,4}$")

#: The change operations a row may declare. ``T`` ("touched") exists only for
#: rows recovered by migration from a ``body-v1`` record: that schema never
#: recorded an operation, so a migrated row attests the path was in the Step's
#: declared scope without inventing which of add/modify/delete happened.
_OPS = frozenset({"A", "M", "D", "R", "T"})

#: The operation a migrated row carries. Kept distinct from the natively
#: logged operations so a reader can always tell recovered evidence from
#: evidence an executor actually reported.
MIGRATED_OP = "T"

#: The label cell of a check row: ``- `S01` `verify:` `<command>` -> `pass```.
VERIFY_LABEL = "verify:"

#: The label cell of an attribution row: ``- `S01` `by:` `<persona>```.
BY_LABEL = "by:"

#: One list row, captured before its backticked cells are split out.
_ROW_RE = re.compile(r"^[ \t]*[-*][ \t]+(?P<cells>.+?)[ \t]*$")

#: A backtick-quoted cell.
_CELL_RE = re.compile(r"`([^`]*)`")

#: The ``## Changes`` section, up to the next level-two heading.
_CHANGES_RE = re.compile(
    r"^##[ \t]+Changes[ \t]*$(?P<body>.*?)(?=^##[ \t]+|\Z)",
    re.MULTILINE | re.DOTALL,
)

#: The ``## Notes`` section, up to the next level-two heading.
_NOTES_RE = re.compile(
    r"^##[ \t]+Notes[ \t]*$(?P<body>.*?)(?=^##[ \t]+|\Z)",
    re.MULTILINE | re.DOTALL,
)

#: A note line: ``- `S01` free text``.
_NOTE_RE = re.compile(
    r"^[ \t]*[-*][ \t]+`(?P<step>S\d{1,4})`[ \t]*(?P<text>.*?)[ \t]*$"
)

#: An HTML comment: template guidance for a reader, never a row. Stripped
#: before any section is parsed so an example inside a hint block cannot
#: register a Step as covered.
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


@dataclass(frozen=True)
class LedgerRow:
    """One parsed ``## Changes`` row.

    Attributes:
        step_id: The row's leading Step identifier, or ``None`` for a
            per-Step record's row (where the document supplies the Step).
        op: The change operation (``A``, ``M``, ``D``, ``R``, ``T``), or
            ``None`` for a non-change row.
        label: The keyword of a non-change row (``verify:`` or ``by:``), or
            ``None`` for a change row.
        paths: The backticked cells after the operation or label, in row
            order. A rename carries two paths; a ``verify:`` row carries the
            command and its result; a ``by:`` row carries the persona.
    """

    step_id: str | None
    op: str | None
    paths: tuple[str, ...]
    label: str | None = None


@dataclass(frozen=True)
class StepEvidence:
    """What a ledger records for one Step.

    Attributes:
        rows: Count of change rows (``A``/``M``/``D``/``R``/``T``).
        verify: The last ``verify:`` result (``pass`` or ``fail``), or
            ``None`` when no check row exists.
        by: The last ``by:`` persona, or ``None``.
    """

    rows: int = 0
    verify: str | None = None
    by: str | None = None


def is_ledger_stem(stem: str) -> bool:
    """Return whether a document stem names a ledger."""
    return stem.endswith(LEDGER_SUFFIX)


def _changes_body(body: str) -> str | None:
    """Return the ``## Changes`` section text, comments stripped, or ``None``."""
    match = _CHANGES_RE.search(body)
    return _COMMENT_RE.sub("", match.group("body")) if match else None


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
        label: str | None = None
        if index < len(cells) and cells[index] in _OPS:
            op = cells[index]
            index += 1
        elif index < len(cells) and cells[index].endswith(":"):
            label = cells[index]
            index += 1

        rows.append(
            LedgerRow(step_id=step_id, op=op, paths=tuple(cells[index:]), label=label)
        )
    return tuple(rows)


def ledger_step_ids(body: str) -> tuple[str, ...]:
    """Return every distinct Step id a ledger body covers, in first-seen order.

    Any ``## Changes`` row naming a Step covers it, including a ``verify:``
    or ``by:`` row: the row was written by the verb at Step close.

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


def ledger_step_evidence(body: str) -> dict[str, StepEvidence]:
    """Summarise the rows of a ledger body per Step.

    Args:
        body: The ledger document body, frontmatter already stripped.

    Returns:
        Map from Step id to its :class:`StepEvidence`, in first-seen order.
    """
    evidence: dict[str, StepEvidence] = {}
    for row in parse_ledger_rows(body):
        if row.step_id is None:
            continue
        current = evidence.get(row.step_id, StepEvidence())
        if row.op is not None:
            current = StepEvidence(current.rows + 1, current.verify, current.by)
        elif row.label == VERIFY_LABEL and row.paths:
            current = StepEvidence(current.rows, row.paths[-1], current.by)
        elif row.label == BY_LABEL and row.paths:
            current = StepEvidence(current.rows, current.verify, row.paths[0])
        evidence[row.step_id] = current
    return evidence


def format_row(step_id: str, op: str, *paths: str) -> str:
    """Render one mechanical ``## Changes`` row.

    Args:
        step_id: The Step the row belongs to (e.g. ``S01``).
        op: The change operation (``A``, ``M``, ``D``, ``R``, ``T``), or a
            label (``verify:``, ``by:``).
        *paths: The paths; for ``verify:`` the command and result; for
            ``by:`` the persona.

    Returns:
        The row text, without a trailing newline.
    """
    cells = " -> ".join(f"`{path}`" for path in paths)
    return f"- `{step_id}` `{op}`{' ' + cells if cells else ''}"


def format_note(step_id: str, text: str) -> str:
    """Render one ``## Notes`` line for *step_id*."""
    return f"- `{step_id}` {' '.join(text.split())}"


def note_lines(body: str) -> tuple[tuple[str | None, str], ...]:
    """Return the ``## Notes`` lines of *body* as ``(step_id, text)`` pairs.

    A line led by a Step cell yields that Step; any other non-empty line
    yields ``None`` with its text, so a per-Step record's free prose can be
    re-keyed by the fold.
    """
    match = _NOTES_RE.search(body)
    if match is None:
        return ()
    notes: list[tuple[str | None, str]] = []
    for line in _COMMENT_RE.sub("", match.group("body")).splitlines():
        if not line.strip():
            continue
        keyed = _NOTE_RE.match(line)
        if keyed:
            notes.append((keyed.group("step"), keyed.group("text")))
        else:
            notes.append((None, line.strip().lstrip("-* ").strip()))
    return tuple(notes)


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
    return _append_to_section(body, match, rows)


def append_notes(body: str, lines: Sequence[str]) -> str:
    """Return *body* with *lines* appended to its ``## Notes`` section.

    The section is created at the end of the document on first use, so a
    ledger with nothing to report carries no ``## Notes`` at all. Lines
    already present verbatim are not appended again.

    Args:
        body: The document body, frontmatter already stripped.
        lines: The rendered note lines to append.

    Returns:
        The updated body.
    """
    if not lines:
        return body
    match = _NOTES_RE.search(body)
    if match is None:
        trimmed = body.rstrip("\n")
        return f"{trimmed}\n\n## Notes\n\n{chr(10).join(lines)}\n"
    return _append_to_section(body, match, lines)


def _append_to_section(body: str, match: re.Match[str], rows: Sequence[str]) -> str:
    """Append the not-yet-present *rows* to the matched section body."""
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
