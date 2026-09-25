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

from .markdown import HTML_COMMENT_RE, INLINE_CODE_RE, find_section

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .markdown import Section

__all__ = [
    "BY_LABEL",
    "LEDGER_SUFFIX",
    "MIGRATED_OP",
    "VERIFY_LABEL",
    "LedgerRow",
    "StepEvidence",
    "append_notes",
    "append_rows",
    "backtick_cells",
    "format_note",
    "format_row",
    "is_ledger_stem",
    "ledger_step_evidence",
    "ledger_step_ids",
    "note_lines",
    "parse_ledger_rows",
    "step_ids_from_rows",
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

#: The section every mechanical row lives in.
_CHANGES = "Changes"

#: The section exception notes live in.
_NOTES = "Notes"

#: A note line: ``- `S01` free text``.
_NOTE_RE = re.compile(
    r"^[ \t]*[-*][ \t]+`(?P<step>S\d{1,4})`[ \t]*(?P<text>.*?)[ \t]*$"
)

#: Characters mdformat rewrites in plain inline text: it escapes each where
#: it could open emphasis, a link, raw HTML, a code span, a character
#: reference or a strikethrough, and the backslash that is an escape itself.
_MARKDOWN_SIGNIFICANT = frozenset("\\*_[]<&~`")

#: One word of a note: a run of non-space characters and code spans, a span
#: kept whole even when it holds a space.
_NOTE_WORD_RE = re.compile(rf"(?:{INLINE_CODE_RE.pattern}|\S)+", re.DOTALL)

#: A run of backticks inside a code span's content.
_BACKTICK_RUN_RE = re.compile(r"`+")


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


def backtick_cells(text: str) -> list[str]:
    """Return the contents of every backtick-quoted cell in *text*, in order."""
    return _CELL_RE.findall(text)


def _section_rows(body: str, title: str) -> str | None:
    """Return a section's text with comments stripped, or ``None`` when absent.

    Comments are template guidance for a reader, never rows: stripping them
    before parsing keeps an example inside a hint block from registering a
    Step as covered.
    """
    section = find_section(body, title)
    return HTML_COMMENT_RE.sub("", section.body) if section is not None else None


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
    section = _section_rows(body, _CHANGES)
    if section is None:
        return ()

    rows: list[LedgerRow] = []
    for line in section.splitlines():
        row_match = _ROW_RE.match(line)
        if row_match is None:
            continue
        cells = backtick_cells(row_match.group("cells"))
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
    return step_ids_from_rows(parse_ledger_rows(body))


def step_ids_from_rows(rows: Sequence[LedgerRow]) -> tuple[str, ...]:
    """Return every distinct Step id in already-parsed ledger *rows*.

    The body-taking :func:`ledger_step_ids` is this plus a parse. Callers that
    need the rows for something else take this form instead, so one pass over
    a ledger serves every question asked of it.

    Args:
        rows: Parsed rows, as :func:`parse_ledger_rows` returns them.

    Returns:
        The Step identifiers, deduplicated and ordered by first appearance.
    """
    seen: dict[str, None] = {}
    for row in rows:
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
    """Render one ``## Notes`` line for *step_id*.

    Whitespace collapses to single spaces, and the line reads back as the
    text was written without any hand escaping. A word holding a character
    markdown would take as syntax - the ``_`` of a private module's path, a
    ``*``, a ``<`` - is set as inline code, as the ledger sets every path in
    its rows; code spans the text already has are kept. Every span is
    written in mdformat's own form, so the line passes the markdown check
    and rendering an already rendered note changes nothing.

    Args:
        step_id: The Step the note belongs to.
        text: The note, as plain text with optional code spans.

    Returns:
        The note line, without a trailing newline.
    """
    words = _NOTE_WORD_RE.finditer(" ".join(text.split()))
    return f"- `{step_id}` {' '.join(_inert_word(m.group()) for m in words)}"


def _inert_word(word: str) -> str:
    """Render one note word so markdown reads it back as written."""
    if _MARKDOWN_SIGNIFICANT.isdisjoint(INLINE_CODE_RE.sub("", word)):
        return INLINE_CODE_RE.sub(lambda span: _code_span(_span_content(span)), word)
    return _code_span(INLINE_CODE_RE.sub(_span_content, word))


def _span_content(span: re.Match[str]) -> str:
    """Return a matched code span's content as CommonMark reads it.

    One space is stripped from each end when both ends have one and the
    content is not all spaces: that pair only pads the span.
    """
    content = span.group(2)
    if content.startswith(" ") and content.endswith(" ") and content.strip():
        return content[1:-1]
    return content


def _code_span(content: str) -> str:
    """Write *content* as a code span in the form mdformat writes one.

    The fence is one backtick longer than the longest run inside, padded by
    a space on each side when there is a run, so the content's own backticks
    neither close the span nor merge with its fence.
    """
    longest = max(map(len, _BACKTICK_RUN_RE.findall(content)), default=0)
    if longest:
        fence = "`" * (longest + 1)
        return f"{fence} {content} {fence}"
    if content.startswith(" ") and content.endswith(" ") and content.strip():
        return f"` {content} `"
    return f"`{content}`"


def note_lines(body: str) -> tuple[tuple[str | None, str], ...]:
    """Return the ``## Notes`` lines of *body* as ``(step_id, text)`` pairs.

    A line led by a Step cell yields that Step; any other non-empty line
    yields ``None`` with its text, so a per-Step record's free prose can be
    re-keyed by the fold.
    """
    section = _section_rows(body, _NOTES)
    if section is None:
        return ()
    notes: list[tuple[str | None, str]] = []
    for line in section.splitlines():
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

    Change rows are deduplicated against the section. Verification and
    attribution batches are deduplicated only against the latest sequence
    for that Step and label, so retries are idempotent without discarding
    a return to an earlier result or worker.

    Args:
        body: The document body, frontmatter already stripped.
        rows: The rendered rows to append.

    Returns:
        The updated body.

    Raises:
        ValueError: If *body* declares no ``## Changes`` section, which means
            the document is not a ledger and appending would invent one.
    """
    section = find_section(body, _CHANGES)
    if section is None:
        message = "document has no '## Changes' section to append to"
        raise ValueError(message)
    history = _evidence_batches(body)
    incoming = _evidence_batches(f"## {_CHANGES}\n\n{chr(10).join(rows)}")
    new_evidence = {
        row
        for key, batch in incoming.items()
        if history.get(key, [])[-len(batch) :] != batch
        for row in batch
    }
    existing = {line.strip() for line in section.body.splitlines() if line.strip()}
    fresh = [
        line
        for line in rows
        if line.strip() not in existing
        or any(
            row in new_evidence for row in parse_ledger_rows(f"## {_CHANGES}\n\n{line}")
        )
    ]
    return _append_to_section(body, section, fresh)


def _evidence_batches(body: str) -> dict[tuple[str | None, str], list[LedgerRow]]:
    """Group evidence by the Step and label whose last row readers use.

    Keep commands together: a repeated command after a different command
    is still new evidence. Comparing whole suffixes also permits an
    idempotent retry of a log containing several checks.
    """
    batches: dict[tuple[str | None, str], list[LedgerRow]] = {}
    for row in parse_ledger_rows(body):
        if row.label is not None and row.label in (VERIFY_LABEL, BY_LABEL):
            batches.setdefault((row.step_id, row.label), []).append(row)
    return batches


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
    section = find_section(body, _NOTES)
    if section is None:
        trimmed = body.rstrip("\n")
        return f"{trimmed}\n\n## {_NOTES}\n\n{chr(10).join(lines)}\n"
    existing = {line.strip() for line in section.body.splitlines() if line.strip()}
    fresh = [line for line in lines if line.strip() not in existing]
    return _append_to_section(body, section, fresh)


def _append_to_section(body: str, section: Section, rows: Sequence[str]) -> str:
    """Append the selected *rows* to *section* of *body*."""
    if not rows:
        return body

    # Rebuild the section in the layout the markdown hygiene check accepts,
    # so an append never leaves the ledger needing a fix: one blank line
    # under the heading, one before the rows when they start a list rather
    # than extend one, and one before the next section, or a single newline
    # when the section ends the document. Repeated appends therefore cannot
    # accumulate whitespace either.
    head = body[: section.start]
    if not head.endswith("\n"):
        head += "\n"
    kept = section.body.strip("\n")
    if kept:
        extends_list = _ROW_RE.match(kept.rsplit("\n", 1)[-1]) is not None
        kept += "\n" if extends_list else "\n\n"
    tail = body[section.end :]
    ending = "\n\n" if tail else "\n"
    return f"{head}\n{kept}{chr(10).join(rows)}{ending}{tail}"
