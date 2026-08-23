"""The bounded-window vocabulary every capped surface speaks.

A cap without a marker is worse than an overflow. An overflow fails loudly;
a silent cut produces a confident wrong answer, because the caller cannot
tell "these are all twenty documents" from "these are twenty of 2,610". So
this module defines a cap and its marker as one object: applying the window
and describing it are the same operation, and a surface cannot do the first
without emitting the second.

Four fields make a bounded contract, and all four are required (a fifth,
``offset``, travels whenever the window is not at the start):

``returned``
    How many rows this response carries.
``total``
    How many existed before the cap. The number that lets a caller decide
    to narrow instead of paging blindly.
``truncated``
    Whether more rows follow this window. Not the same as "fewer rows came
    back than matched" once ``offset`` is non-zero, and it is the first
    that a caller can act on.
``next_offset``
    Where to resume, or ``None`` at the end. Paging is not optional: a cap
    with no way past it converts a saturation failure into a workflow one.

It lives in the shared core rather than under the CLI because bounding a
return is a property of the domain, not of one presentation: the repair
pipeline bounds its nested diagnostics with the same vocabulary the CLI uses
for its listings, and neither should depend on the other to do it.

The window is computed once, before the format branch, so the JSON payload
and the human rendering read the same numbers and cannot drift. The human
surface previously carried caps the machine surface did not, and each was
free to disagree with the other about what had been dropped.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["Window", "apply_window", "elision_line", "windowed_section"]

#: Rows returned when a caller names no limit. Chosen to sit inside the
#: listing budget for a row of typical width rather than to be a round
#: number; a surface whose rows are unusually wide should pass its own.
DEFAULT_LIMIT = 50

#: The largest window a caller may request. A caller that wants everything
#: is a caller that has not yet been told the total, and this is the ceiling
#: that makes that true - it cannot be raised from the request.
MAX_LIMIT = 500


@dataclass(frozen=True)
class Window:
    """The bounded slice of a collection that one response carries.

    Attributes:
        total: Rows that matched before the cap was applied.
        returned: Rows actually carried by this response.
        offset: Index of the first returned row within the full result.
    """

    total: int
    returned: int
    offset: int = 0

    @property
    def truncated(self) -> bool:
        """Whether more matching rows follow this window."""
        return self.offset + self.returned < self.total

    @property
    def next_offset(self) -> int | None:
        """The offset that resumes after this window, or ``None`` at the end."""
        nxt = self.offset + self.returned
        return nxt if nxt < self.total else None

    def as_fields(self) -> dict[str, object]:
        """Render the window as envelope keys.

        ``truncated`` means "more rows follow this window", not "fewer rows
        were returned than matched" - the two differ once ``offset`` is
        non-zero, and only the first is actionable.

        ``offset`` is emitted whenever it is non-zero. Without it a window
        positioned past the end of the result reports ``returned: 0``,
        ``total: 2610``, ``truncated: false``, which reads as "these are all
        of them" - a marker that misleads is the defect this vocabulary
        exists to prevent, so the position that explains the zero travels
        with it.

        Returns:
            The contract fields, with ``next_offset`` present only when there
            is more to fetch and ``offset`` only when the window is not at
            the start.
        """
        fields: dict[str, object] = {
            "returned": self.returned,
            "total": self.total,
            "truncated": self.truncated,
        }
        if self.offset:
            fields["offset"] = self.offset
        if self.next_offset is not None:
            fields["next_offset"] = self.next_offset
        return fields


def _resolve_limit(limit: int | None) -> int:
    """Clamp a caller's limit into the permitted range.

    Args:
        limit: The requested cap, or ``None`` for the default.

    Returns:
        A limit within ``1..MAX_LIMIT``. A non-positive request is treated as
        the default rather than as a slice bound - a negative limit reaching
        a Python slice silently returns nearly everything, which is precisely
        the failure this module exists to prevent.
    """
    if limit is None or limit <= 0:
        return DEFAULT_LIMIT
    return min(limit, MAX_LIMIT)


def apply_window[T](
    rows: Sequence[T],
    *,
    limit: int | None = None,
    offset: int = 0,
) -> tuple[list[T], Window]:
    """Cut *rows* to a bounded window and describe what was cut.

    Returning the slice and its description together is the point: a caller
    cannot take the rows and forget the marker, because the marker arrives in
    the same expression.

    Args:
        rows: The full matched result, in display order.
        limit: Maximum rows to return. ``None`` uses :data:`DEFAULT_LIMIT`;
            values above :data:`MAX_LIMIT` are clamped down.
        offset: Rows to skip, for resuming a previous window. Negative
            offsets are treated as zero.

    Returns:
        The bounded rows and the :class:`Window` describing them.
    """
    total = len(rows)
    start = max(0, offset)
    end = start + _resolve_limit(limit)
    window_rows = list(rows[start:end])
    return window_rows, Window(total=total, returned=len(window_rows), offset=start)


def windowed_section[T](
    rows: Sequence[T],
    *,
    limit: int | None = None,
    offset: int = 0,
) -> dict[str, object]:
    """Render one payload section as a bounded, self-describing object.

    For payloads built from several independently-growing lists, where each
    section needs its own cap and its own marker. Returning ``{"items": ...}``
    beside the window fields keeps the count attached to the rows it counts,
    rather than to a sibling key that can be dropped or read separately.

    Args:
        rows: The section's full contents.
        limit: Maximum rows to carry; ``None`` uses :data:`DEFAULT_LIMIT`.
        offset: Rows to skip, for resuming a previous window.

    Returns:
        ``items`` plus the window's contract fields.
    """
    items, window = apply_window(rows, limit=limit, offset=offset)
    section: dict[str, object] = {"items": items}
    section.update(window.as_fields())
    return section


def elision_line(window: Window, noun: str) -> str | None:
    """Render the human surface's one-line notice of what was withheld.

    Derived from the same :class:`Window` the JSON payload reports, so the
    two renderings cannot disagree about what was dropped.

    Args:
        window: The window applied to the response.
        noun: Plural noun for the elided rows, e.g. ``"documents"``.

    Returns:
        The notice, or ``None`` when nothing was withheld.
    """
    if not window.truncated:
        return None
    hidden = window.total - (window.offset + window.returned)
    return (
        f"... {hidden:,} more {noun} "
        f"({window.total:,} total; --offset {window.next_offset} for the next page)"
    )
