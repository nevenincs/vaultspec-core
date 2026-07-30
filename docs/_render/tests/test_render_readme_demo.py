"""Guards for the committed README pipeline-demo generator.

Rendering the GIF needs the ``agg`` binary and a full pipeline run, but the
stream it feeds ``agg`` is synthesized in pure Python: an asciicast v2 header,
a monotonic clock, and the line-fitting that keeps captured output inside the
demo terminal. A malformed cast is not a rendering glitch - ``agg`` refuses it
outright - so the format is worth pinning.

Like :mod:`docs._render.tests.test_render_readme_assets`, this module imports inside
the test bodies: :mod:`docs._render.render_readme_demo` deletes ``NO_COLOR`` from the
process environment at import time.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("preserved_no_color")]

#: One ``agg`` theme channel: six lowercase hex digits, no ``#`` prefix.
HEX_CHANNEL = re.compile(r"[0-9a-f]{6}")

#: The ANSI palette an ``agg`` theme string carries after background and
#: foreground: the eight normal colours followed by their bright variants.
ANSI_COLORS = 16


def test_fit_lines_drops_trailing_blank_lines() -> None:
    """Captured output ends where the command's last line ends."""
    from docs._render.render_readme_demo import fit_lines

    assert fit_lines("first\nsecond\n\n\n   \n", width=40) == ["first", "second"]


def test_fit_lines_ellipsis_trims_to_the_demo_terminal_width() -> None:
    """An over-long capture is cut to the frame, with the cut made visible."""
    from docs._render.render_readme_demo import fit_lines

    lines = fit_lines("x" * 200, width=20)

    assert len(lines) == 1
    assert len(lines[0]) <= 20
    assert lines[0].endswith("…")


def test_fit_lines_leaves_short_lines_untouched() -> None:
    """Nothing is trimmed when the capture already fits."""
    from docs._render.render_readme_demo import fit_lines

    assert fit_lines("short", width=40) == ["short"]


def test_cast_clock_never_runs_backwards() -> None:
    """asciicast timestamps must be non-decreasing or the player desynchronises."""
    from docs._render.render_readme_demo import Cast

    cast = Cast()
    cast.type_line("vaultspec-core status")
    cast.stream(["one", "two", "three"])
    cast.emit("", 1.5)

    stamps = [t for t, _data in cast.events]
    assert stamps == sorted(stamps)
    assert stamps[0] > 0


def test_cast_stream_emits_every_line_it_is_given() -> None:
    """Chunking output two lines at a time must not drop the odd last line."""
    from docs._render.render_readme_demo import Cast

    cast = Cast()
    cast.stream(["one", "two", "three"])

    assert "".join(data for _t, data in cast.events) == "one\r\ntwo\r\nthree\r\n"


def test_cast_dump_writes_a_valid_asciicast_v2_stream(tmp_path: Path) -> None:
    """``agg`` refuses anything that is not header-then-events JSON lines."""
    from docs._render.render_readme_demo import COLS, ROWS, Cast

    cast = Cast()
    cast.stream(["one", "two"])
    out = tmp_path / "demo.cast"
    cast.dump(str(out), "vaultspec pipeline demo")

    lines = out.read_text(encoding="utf-8").splitlines()
    header = json.loads(lines[0])
    assert header == {
        "version": 2,
        "width": COLS,
        "height": ROWS,
        "title": "vaultspec pipeline demo",
    }

    events = [json.loads(line) for line in lines[1:]]
    assert events, "the cast carries no output events"
    for event in events:
        assert len(event) == 3
        assert isinstance(event[0], float)
        assert event[1] == "o"
        assert isinstance(event[2], str)
    assert [event[0] for event in events] == [t for t, _data in cast.events]


def test_agg_theme_is_derived_from_the_svg_palette() -> None:
    """The GIF and the still renders must not drift onto different palettes."""
    from docs._render.render_readme_assets import VAULTSPEC_THEME
    from docs._render.render_readme_demo import AGG_THEME

    def as_hex(triplet: tuple[int, int, int]) -> str:
        return "".join(f"{component:02x}" for component in triplet)

    channels = AGG_THEME.split(",")
    assert all(HEX_CHANNEL.fullmatch(channel) for channel in channels), AGG_THEME
    assert channels == [
        as_hex(VAULTSPEC_THEME.background_color),
        as_hex(VAULTSPEC_THEME.foreground_color),
        *(as_hex(VAULTSPEC_THEME.ansi_colors[index]) for index in range(ANSI_COLORS)),
    ]
