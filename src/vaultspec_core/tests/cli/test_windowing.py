"""Tests for the bounded-window vocabulary shared by every capped surface.

These pin the contract itself rather than any one command: that a cap always
travels with a marker, that the marker cannot read as "these are all of them"
when it is not, that a hostile limit cannot widen the window, and that the
human notice is derived from the same numbers the JSON payload reports so the
two surfaces cannot drift.

The negative-limit case is a regression test with a real origin: the ``find``
tool declared an unbounded ``limit`` that reached a Python slice, so
``limit=-1`` silently returned 128 of 129 rows instead of erroring.
"""

from __future__ import annotations

import pytest

from vaultspec_core.core.windowing import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    Window,
    apply_window,
    elision_line,
)

pytestmark = [pytest.mark.unit]


def _rows(count: int) -> list[dict[str, object]]:
    """Build *count* trivial rows."""
    return [{"i": i} for i in range(count)]


def test_a_cap_always_reports_the_total_it_cut_from() -> None:
    """A windowed response says how many rows existed before the cap."""
    rows, window = apply_window(_rows(2610), limit=20)

    assert len(rows) == 20
    assert window.as_fields() == {
        "returned": 20,
        "total": 2610,
        "truncated": True,
        "next_offset": 20,
    }


def test_an_uncut_result_is_not_marked_truncated() -> None:
    """A result that fits carries no next offset and no truncation flag."""
    _, window = apply_window(_rows(5), limit=20)

    assert window.truncated is False
    assert window.next_offset is None
    assert "next_offset" not in window.as_fields()


def test_the_final_page_reports_nothing_follows() -> None:
    """Exhausting the result clears the marker even at a non-zero offset."""
    rows, window = apply_window(_rows(2610), limit=20, offset=2600)

    assert len(rows) == 10
    assert window.truncated is False
    assert window.next_offset is None


def test_a_window_past_the_end_reports_its_offset() -> None:
    """A zero-row window says where it was positioned.

    Without the offset this reads ``returned: 0, total: 2610,
    truncated: false``, which is indistinguishable from "these are all of
    them" - the misleading marker the vocabulary exists to prevent.
    """
    _, window = apply_window(_rows(2610), limit=20, offset=5000)

    fields = window.as_fields()
    assert fields["returned"] == 0
    assert fields["total"] == 2610
    assert fields["offset"] == 5000


def test_a_negative_limit_does_not_widen_the_window() -> None:
    """A negative limit falls back to the default instead of slicing.

    Regression: a bare ``int`` limit reaching ``rows[:limit]`` turned
    ``limit=-1`` into "everything but the last row".
    """
    rows, window = apply_window(_rows(2610), limit=-1)

    assert len(rows) == DEFAULT_LIMIT
    assert window.returned == DEFAULT_LIMIT
    assert window.total == 2610


def test_an_oversized_limit_is_clamped_to_the_ceiling() -> None:
    """A caller cannot raise the ceiling from the request."""
    rows, _ = apply_window(_rows(2610), limit=10_000)

    assert len(rows) == MAX_LIMIT


def test_the_human_notice_is_derived_from_the_same_window() -> None:
    """The text elision reports the JSON window's own numbers."""
    _, window = apply_window(_rows(2610), limit=20)
    notice = elision_line(window, "documents")

    assert notice is not None
    assert "2,590 more documents" in notice
    assert "2,610 total" in notice
    assert f"--offset {window.next_offset}" in notice


def test_no_notice_when_nothing_was_withheld() -> None:
    """A complete result prints no elision line."""
    _, window = apply_window(_rows(5), limit=20)

    assert elision_line(window, "documents") is None


def test_window_fields_never_promise_more_than_they_know() -> None:
    """``truncated`` tracks whether rows follow, not whether rows were cut."""
    assert Window(total=10, returned=10, offset=0).truncated is False
    assert Window(total=10, returned=5, offset=0).truncated is True
    assert Window(total=10, returned=5, offset=5).truncated is False
