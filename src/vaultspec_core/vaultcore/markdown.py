"""Fence-aware markdown structure: code fences, ATX headings, and excerpt blocks.

Every scanner that asks "is this line code?" or "is this line a heading?"
must give the same answer, or the checks, the section editor, and the search
corpus disagree about the same document. Each partial reading misfires on a
different document: a detector that toggles on any fence-looking line lets a
nested sample escape its outer fence, one that ignores the closing run's
length ends a four-backtick fence at a quoted three-backtick line, and a
section scanner that ignores fences ends a section at a ``# =====`` comment
inside a shell sample. This module is the one definition, and every such
scanner is built on it.

The rules are the CommonMark subset a line scanner can apply without a full
block parser:

- A **fence** opens on a line indented by at most three spaces that starts a
  run of three or more backticks or tildes; a backtick fence's info string
  may not contain a backtick. It closes on a line indented by at most three
  spaces holding a run of the same character at least as long as the opener,
  followed only by whitespace. A fence left unclosed runs to the end of the
  text: a document cannot end inside a code sample and have the tail read as
  prose.
- An **ATX heading** is a line outside any fence indented by at most three
  spaces, holding one to six ``#`` followed by a space, a tab, or the end of
  the line. An optional closing run of ``#`` preceded by whitespace is not
  part of the text.

Setext headings, indented code blocks, list nesting, and HTML blocks are out
of scope: no vault document depends on them for structure, and modelling them
would need the block parser this module exists to avoid.

Lines are split on ``\\n`` only. A trailing ``\\r`` from CRLF text is treated
as line-ending whitespace by every rule, so callers need not normalise first,
and the excerpt blocks stay verbatim slices of whatever text was passed in.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from enum import StrEnum
from itertools import pairwise
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

__all__ = [
    "Block",
    "FenceTracker",
    "Heading",
    "LineRole",
    "document_title",
    "iter_headings",
    "line_roles",
    "paragraph_blocks",
    "parse_atx_heading",
]

#: Whitespace a rule may ignore at a line's edges: CommonMark's spaces and
#: tabs, plus the line-ending characters a caller's split may leave attached.
_LINE_WHITESPACE = " \t\r\n"

#: A fence-shaped line: up to three spaces, a run of three or more backticks
#: or tildes, and whatever follows on the line.
_FENCE_RE = re.compile(r" {0,3}(?P<run>`{3,}|~{3,})(?P<rest>.*)")

#: An ATX heading line with its line ending removed. The hashes must be
#: followed by a space, a tab, or nothing at all.
_ATX_RE = re.compile(r" {0,3}(?P<hashes>#{1,6})(?:[ \t](?P<rest>.*))?")

#: The optional closing sequence of an ATX heading: a run of ``#`` that is the
#: whole content or is preceded by whitespace.
_CLOSING_HASHES_RE = re.compile(r"(?:^|[ \t]+)#+$")


class LineRole(StrEnum):
    """What one line is with respect to fenced code blocks."""

    TEXT = "text"
    """Outside every fence."""

    FENCE_OPEN = "fence-open"
    """The delimiter line that opens a fence."""

    CODE = "code"
    """A line inside an open fence, blank or not."""

    FENCE_CLOSE = "fence-close"
    """The delimiter line that closes a fence."""

    @property
    def fenced(self) -> bool:
        """Whether the line belongs to a fenced code block, delimiters included."""
        return self is not LineRole.TEXT


class FenceTracker:
    """Classify lines one at a time, carrying the open fence between them.

    Most callers want :func:`line_roles`. The tracker exists for scanners
    whose own state decides whether a line is eligible to open a fence at all
    - a line inside a multi-line HTML comment is comment text, not a fence -
    so they feed it only the lines that can carry markdown structure.
    """

    __slots__ = ("_char", "_length")

    def __init__(self) -> None:
        self._char = ""
        self._length = 0

    def classify(self, line: str) -> LineRole:
        """Return *line*'s role and advance past it.

        Args:
            line: One line, with or without its line ending.

        Returns:
            The line's :class:`LineRole` given every line fed before it.
        """
        match = _FENCE_RE.match(line)
        if not self._char:
            if match is None:
                return LineRole.TEXT
            run = match.group("run")
            if run[0] == "`" and "`" in match.group("rest"):
                return LineRole.TEXT
            self._char, self._length = run[0], len(run)
            return LineRole.FENCE_OPEN
        if (
            match is not None
            and match.group("run")[0] == self._char
            and len(match.group("run")) >= self._length
            and not match.group("rest").strip(_LINE_WHITESPACE)
        ):
            self._char, self._length = "", 0
            return LineRole.FENCE_CLOSE
        return LineRole.CODE


def line_roles(lines: Iterable[str]) -> list[LineRole]:
    """Classify every line of a document against its fenced code blocks.

    Takes lines rather than text so each caller keeps its own split: the
    returned roles align index for index with the lines it passed.

    Args:
        lines: The document's lines, in order, with or without line endings.

    Returns:
        One :class:`LineRole` per input line.
    """
    tracker = FenceTracker()
    return [tracker.classify(line) for line in lines]


def parse_atx_heading(line: str) -> tuple[int, str] | None:
    """Parse *line* as an ATX heading, without regard to fences.

    For callers that already know the line lies outside every fence; use
    :func:`iter_headings` to scan a whole document.

    Args:
        line: One line, with or without its line ending.

    Returns:
        ``(level, text)`` where *text* has its surrounding whitespace and
        closing ``#`` run removed and its inline markdown intact, or ``None``
        when the line is not a heading.
    """
    match = _ATX_RE.fullmatch(line.rstrip("\r\n"))
    if match is None:
        return None
    content = (match.group("rest") or "").strip(" \t")
    text = _CLOSING_HASHES_RE.sub("", content)
    return len(match.group("hashes")), text


@dataclass(frozen=True)
class Heading:
    """One ATX heading found outside fenced code.

    Attributes:
        level: The number of ``#`` characters, 1 to 6.
        text: The heading text without surrounding whitespace or the closing
            ``#`` run; inline markdown is left intact.
        line: The heading's 1-based line number within the scanned text.
    """

    level: int
    text: str
    line: int


def iter_headings(text: str) -> Iterator[Heading]:
    """Yield the ATX headings of *text*, skipping everything inside fences.

    Args:
        text: Markdown text; lines are split on ``\\n``.

    Yields:
        Each :class:`Heading` in document order.
    """
    tracker = FenceTracker()
    for number, line in enumerate(text.split("\n"), start=1):
        if tracker.classify(line) is not LineRole.TEXT:
            continue
        parsed = parse_atx_heading(line)
        if parsed is not None:
            yield Heading(level=parsed[0], text=parsed[1], line=number)


def document_title(text: str) -> str | None:
    """Return the text of the first non-empty level-one heading outside fences.

    Args:
        text: A markdown body, without frontmatter: a YAML comment line would
            otherwise read as a heading.

    Returns:
        The title with its inline markdown intact, or ``None`` when the text
        has no titled H1.
    """
    return next(
        (
            heading.text
            for heading in iter_headings(text)
            if heading.level == 1 and heading.text
        ),
        None,
    )


@dataclass(frozen=True)
class Block:
    """A verbatim run of document lines, sized for use as an excerpt.

    Attributes:
        heading_path: The titles of the enclosing headings of level two and
            deeper, outermost first. The level-one title is the document's
            name, not a section, so it never enters the path; text before the
            first level-two heading has the path ``()``.
        line_start: The first line of the block, 1-based.
        line_end: The last line of the block, 1-based and inclusive.
        text: Exactly those lines of the source joined by ``\\n``; never
            normalised, so a caller can cite the block by its line range.
    """

    heading_path: tuple[str, ...]
    line_start: int
    line_end: int
    text: str


@dataclass(frozen=True)
class _Span:
    """A candidate block as a half-open, 0-based line range."""

    path: tuple[str, ...]
    start: int
    end: int
    joinable: bool
    """No heading line separates this span from the one before it."""


def _line_starts(lines: list[str]) -> list[int]:
    """Return the character offset of each line in the joined text, plus the end."""
    starts = [0]
    for line in lines:
        starts.append(starts[-1] + len(line) + 1)
    return starts


def _span_length(starts: list[int], start: int, end: int) -> int:
    """Return the character length of lines ``start..end`` joined by ``\\n``."""
    return starts[end] - starts[start] - 1


def _enter_heading(path: list[tuple[int, str]], level: int, text: str) -> None:
    """Close every open section at *level* or deeper, then open this heading's."""
    while path and path[-1][0] >= level:
        path.pop()
    if level >= 2:
        path.append((level, text))


def _content_spans(lines: list[str]) -> list[_Span]:
    """Split *lines* into runs broken by blank lines and headings outside fences.

    A fenced block, its delimiters, and the blank lines inside it are content,
    so a code sample is never cut at its own blank lines, and a fence touching
    a paragraph joins it.
    """
    tracker = FenceTracker()
    path: list[tuple[int, str]] = []
    spans: list[_Span] = []
    start: int | None = None
    joinable = False
    heading_since_span = False
    for index, line in enumerate(lines):
        role = tracker.classify(line)
        heading = parse_atx_heading(line) if role is LineRole.TEXT else None
        if heading is None and (role.fenced or line.strip(_LINE_WHITESPACE)):
            if start is None:
                start, joinable = index, not heading_since_span
                heading_since_span = False
            continue
        if start is not None:
            titles = tuple(title for _, title in path)
            spans.append(_Span(titles, start, index, joinable))
            start = None
        if heading is not None:
            _enter_heading(path, *heading)
            heading_since_span = True
    if start is not None:
        # Only a fence left open at the end can carry blank lines this far;
        # they are the text's trailing newlines, not code.
        end = len(lines)
        while not lines[end - 1].strip(_LINE_WHITESPACE):
            end -= 1
        titles = tuple(title for _, title in path)
        spans.append(_Span(titles, start, end, joinable))
    return spans


def _split_oversized(span: _Span, starts: list[int], max_chars: int) -> list[_Span]:
    """Cut *span* at line boundaries into pieces of at most *max_chars*.

    A single line longer than *max_chars* becomes a piece of its own rather
    than being cut mid-line: an excerpt that splits a line is no longer a
    verbatim slice of the source.
    """
    if _span_length(starts, span.start, span.end) <= max_chars:
        return [span]
    cuts = [span.start]
    for index in range(span.start + 1, span.end):
        if _span_length(starts, cuts[-1], index + 1) > max_chars:
            cuts.append(index)
    # Pieces of one span have no heading between them. Letting them rejoin is
    # safe: each cut exists because the two sides together exceed max_chars,
    # which the merge refuses.
    return [
        replace(
            span, start=start, end=end, joinable=start != span.start or span.joinable
        )
        for start, end in pairwise([*cuts, span.end])
    ]


def _merge_small(
    spans: list[_Span], starts: list[int], *, max_chars: int, min_chars: int
) -> list[_Span]:
    """Fold each span into the one before it while that one is below *min_chars*.

    A span is folded only when no heading separates the two (so both share a
    heading path and the result holds no heading line) and the merged span
    still fits *max_chars*: the maximum is a bound, the minimum only a target.
    """
    merged: list[_Span] = []
    for span in spans:
        if merged and span.joinable:
            last = merged[-1]
            if (
                _span_length(starts, last.start, last.end) < min_chars
                and _span_length(starts, last.start, span.end) <= max_chars
            ):
                merged[-1] = replace(last, end=span.end)
                continue
        merged.append(span)
    return merged


def paragraph_blocks(
    text: str, *, max_chars: int = 1400, min_chars: int = 240
) -> list[Block]:
    """Split *text* into verbatim blocks for excerpting.

    A block starts as a run of consecutive lines broken by blank lines and
    headings outside fences; a fenced code block stays whole within its run.
    Heading lines are never block content; they set the ``heading_path`` of
    the blocks after them. Adjacent blocks with no heading between them merge
    while the accumulated block is shorter than *min_chars* and the result
    fits *max_chars*. A block longer than *max_chars* is split at line
    boundaries, and a single line longer than *max_chars* stays whole.

    Every block is a verbatim slice: its ``text`` equals the source lines
    ``line_start`` through ``line_end`` joined by ``\\n``.

    Args:
        text: A markdown body, without frontmatter; lines are split on
            ``\\n`` and numbered from 1.
        max_chars: The size bound a block is split to respect.
        min_chars: The size below which a block absorbs its successor.

    Returns:
        The blocks in document order.

    Raises:
        ValueError: If *max_chars* is not positive.
    """
    if max_chars < 1:
        raise ValueError(f"max_chars must be positive, got {max_chars}")
    lines = text.split("\n")
    starts = _line_starts(lines)
    pieces = [
        piece
        for span in _content_spans(lines)
        for piece in _split_oversized(span, starts, max_chars)
    ]
    return [
        Block(
            heading_path=span.path,
            line_start=span.start + 1,
            line_end=span.end,
            text=text[starts[span.start] : starts[span.end] - 1],
        )
        for span in _merge_small(
            pieces, starts, max_chars=max_chars, min_chars=min_chars
        )
    ]
