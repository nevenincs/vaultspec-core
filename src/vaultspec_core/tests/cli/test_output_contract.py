"""The output-contract invariants (cli-output-standardization ADR).

Two guarantees are pinned here as enforceable tests rather than left
aspirational: the rendered data surface is byte-identical regardless of the
terminal width, and no shape ever emits a box-drawing glyph. A regression in
either - a future surface that reaches for a Rich ``Table`` again, or a width
that leaks into layout - fails the build instead of slipping through review.
"""

from __future__ import annotations

import os

import pytest

from vaultspec_core.cli.rendering import (
    Column,
    Field,
    TreeLine,
    render_dry_run_tree,
    render_install_summary,
    render_listing,
    render_record,
    render_tree,
    render_uninstall_summary,
    truncate,
)
from vaultspec_core.console import reset_console
from vaultspec_core.core.dry_run import DryRunItem, DryRunStatus


def _box_glyphs(text: str) -> set[str]:
    """Return any Unicode box-drawing characters (U+2500..U+257F) in ``text``."""
    return {ch for ch in text if "─" <= ch <= "╿"}


def _render_at_width(width: int, render, capsys) -> str:
    """Render under a forced ``COLUMNS`` width and return captured stdout.

    Rich reads ``COLUMNS`` for width on a non-tty stream, so this is how an
    environment's width is simulated. The console singleton is reset before and
    after so the width takes effect and does not leak into other tests.
    """
    previous = os.environ.get("COLUMNS")
    os.environ["COLUMNS"] = str(width)
    reset_console()
    try:
        render()
        return capsys.readouterr().out
    finally:
        if previous is None:
            os.environ.pop("COLUMNS", None)
        else:
            os.environ["COLUMNS"] = previous
        reset_console()


# A long value (wider than the narrow test width) is the whole point: if width
# leaked into layout, the narrow render would wrap or pad and diverge.
_LONG = "this-is-a-deliberately-long-value-wider-than-any-narrow-terminal-width"
_ROWS = [
    {"name": "vaultspec-system", "source": "builtin"},
    {"name": _LONG, "source": "project"},
]
_COLS = [Column("name"), Column("source")]


@pytest.mark.unit
class TestWidthDeterminism:
    """Identical bytes under a 30-column and a 200-column environment."""

    def test_listing_is_width_independent(self, capsys):
        def render():
            render_listing(_ROWS, _COLS, title="Rules", summary="2 rules")

        narrow = _render_at_width(30, render, capsys)
        wide = _render_at_width(200, render, capsys)
        assert narrow == wide
        assert _LONG in narrow  # the long value rendered whole, not wrapped

    def test_record_is_width_independent(self, capsys):
        def render():
            render_record(
                [Field("status", "drifted"), Field("detail", _LONG)], title="Status"
            )

        assert _render_at_width(30, render, capsys) == _render_at_width(
            200, render, capsys
        )

    def test_tree_is_width_independent(self, capsys):
        def render():
            render_tree(
                [TreeLine("feature", 0), TreeLine(_LONG, 1, glyph="+")], title="Graph"
            )

        assert _render_at_width(30, render, capsys) == _render_at_width(
            200, render, capsys
        )


@pytest.mark.unit
class TestNoBoxDrawing:
    """No shape in the data path emits a box-drawing glyph."""

    def setup_method(self):
        reset_console()

    def teardown_method(self):
        reset_console()

    def test_listing_has_no_box_glyphs(self, capsys):
        render_listing(_ROWS, _COLS, title="Rules", summary="2 rules")
        assert _box_glyphs(capsys.readouterr().out) == set()

    def test_record_has_no_box_glyphs(self, capsys):
        render_record([Field("status", "ok"), Field("count", "3")], title="Status")
        assert _box_glyphs(capsys.readouterr().out) == set()

    def test_tree_has_no_box_glyphs(self, capsys):
        render_tree(
            [TreeLine("a", 0), TreeLine("b", 1, glyph="+"), TreeLine("c", 2)],
            title="Graph",
        )
        assert _box_glyphs(capsys.readouterr().out) == set()

    def test_dry_run_tree_has_no_box_glyphs(self, capsys):
        items = [
            DryRunItem(path="a.md", status=DryRunStatus.NEW, label="claude"),
            DryRunItem(path="b.md", status=DryRunStatus.UPDATE, label="claude"),
            DryRunItem(path="c.md", status=DryRunStatus.EXISTS),
        ]
        render_dry_run_tree(items, title="Preview")
        assert _box_glyphs(capsys.readouterr().out) == set()

    def test_install_summary_has_no_box_glyphs(self, capsys):
        render_install_summary(
            {"rules": 1, "skills": 2, "agents": 9},
            path="/tmp/x",
            providers=["claude"],
            has_mcp=True,
        )
        assert _box_glyphs(capsys.readouterr().out) == set()

    def test_uninstall_summary_has_no_box_glyphs(self, capsys):
        render_uninstall_summary(
            [("/tmp/x/.claude", "claude (provider)")], path="/tmp/x"
        )
        assert _box_glyphs(capsys.readouterr().out) == set()


@pytest.mark.unit
class TestEncodingInvariance:
    """The second half of the contract: output is stdout-encoding independent.

    Width-independence is proved above; this proves encoding-independence. With
    ASCII data, every *structural* byte a shape emits - the header, the two-space
    indent, the single-space separators, the tree glyphs, the summary line, the
    truncation marker - is ASCII, so there is no box-drawing glyph for the
    cp1252 ``safe_box`` path to down-convert and a UTF-8 versus a legacy stdout
    render byte-identically. Asserting the structure is ASCII pins that directly.
    """

    def setup_method(self):
        reset_console()

    def teardown_method(self):
        reset_console()

    def test_listing_structure_is_ascii(self, capsys):
        render_listing(_ROWS, _COLS, title="Rules", summary="2 rules")
        assert capsys.readouterr().out.isascii()

    def test_record_structure_is_ascii(self, capsys):
        render_record(
            [Field("status", "ok"), Field("detail", truncate("x" * 200, 50))],
            title="Status",
        )
        assert capsys.readouterr().out.isascii()

    def test_tree_structure_is_ascii(self, capsys):
        render_tree(
            [TreeLine("a", 0), TreeLine("b", 1, glyph="+"), TreeLine("c", 2)],
            title="Graph",
        )
        out = capsys.readouterr().out
        assert out.isascii()
        assert "..." not in out  # short labels are not truncated
