"""The reply budget a search page must fit, and the worst-case page to test it.

Both search surfaces - the MCP ``search`` tool and ``vault search --json`` -
carry the same hits, bounded once by the search package. Their size tests
share this module so they measure the same worst case against the same
budget.

The worst case is built by the search package's own bounding, from text fed
far past every cap: titles, five-level heading paths, and excerpt blocks whose
lines are in the scripts that cost the most bytes per character. Line length
matters as much as the script, because JSON spends two bytes on each newline:
a block of one-character lines costs a quarter more on the wire than the same
bytes in paragraph lines.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from vaultspec_core.search import (
    EXCERPT_BYTES,
    MAX_RESULTS,
    SUPPORTING_BYTES,
    SearchHit,
)
from vaultspec_core.search._corpus import SECTION_BYTES, TITLE_BYTES, Record
from vaultspec_core.search._engine import Judgment, search_hit
from vaultspec_core.vaultcore.markdown import Block
from vaultspec_core.vaultcore.models import DocType

__all__ = [
    "BYTES_PER_TOKEN",
    "DISCOVERY_BUDGET",
    "REPLY_CEILING",
    "WORST_SHAPES",
    "worst_case_ranking",
]

#: Bytes of reply JSON per token, as the envelope budgets are measured.
BYTES_PER_TOKEN: Final = 3.46

#: The discovery reply budget, in tokens, that a default page must fit.
DISCOVERY_BUDGET: Final = 4_000

#: The ceiling no single reply may exceed, in tokens, whatever the limit.
REPLY_CEILING: Final = 10_000

#: Worst-case excerpt text, as ``(unit, units per line)``: CJK ideographs at
#: three bytes, emoji at four, each in paragraph lines and one per line, and
#: ASCII prose carrying the quotes and backslashes JSON escapes as vault prose
#: does. Text made of nothing but quotes would cost up to twice its bytes on
#: the wire: the caps bound UTF-8 bytes, not JSON escapes.
WORST_SHAPES: Final[dict[str, tuple[str, int]]] = {
    "cjk-paragraphs": ("\N{CJK UNIFIED IDEOGRAPH-4E2D}", 40),
    "cjk-one-per-line": ("\N{CJK UNIFIED IDEOGRAPH-4E2D}", 1),
    "emoji-paragraphs": ("\N{GRINNING FACE}", 30),
    "emoji-one-per-line": ("\N{GRINNING FACE}", 1),
    "escaped-prose": ('The "budget" caps `find` at C:\\vault\\adr; see the ADR. ', 2),
}

#: A stem and feature tag as long as the longest this repository's vault
#: holds. Both are kebab-case ASCII, so their length is their size.
_LONG_STEM: Final = "2026-01-02-widget-storage-envelope-budget-ceiling-layout-topic"
_LONG_FEATURE: Final = "widget-storage-envelope-budget-ceiling"

#: The deepest heading path a block can have: levels two to six.
_DEEPEST_PATH: Final = 5

#: The widest line the shapes above produce, in bytes; whole-line clipping
#: stops at most this far short of a cap.
_WIDEST_LINE: Final = 120


def _worst_case_hit(index: int, unit: str, per_line: int) -> SearchHit:
    """One hit bounded by the search package from text far past every cap."""
    oversized = unit * 200
    line = unit * per_line

    def block(start: int) -> Block:
        return Block(
            heading_path=(oversized,) * _DEEPEST_PATH,
            line_start=start,
            line_end=start + 999,
            text="\n".join([line] * 1000),
        )

    stem = f"{_LONG_STEM}-{index:02d}-research"
    record = Record(
        name=stem,
        path=Path(f"{stem}.md"),
        rel_path=f".vault/research/{stem}.md",
        doc_type=DocType.RESEARCH,
        feature=_LONG_FEATURE,
        date="2026-01-02",
        title=oversized,
        body="",
        body_line=1,
    )
    judged = Judgment(
        record, 0.912345, 0.5, 0.012345, block(120), block(2_000), "0" * 40
    )
    return search_hit(judged, 0.876543)


def _assert_at_every_cap(hit: SearchHit) -> None:
    """Fail unless *hit* reaches every cap, so the worst case is not a light one."""
    assert hit.excerpt is not None
    assert hit.supporting is not None
    assert len(hit.title.encode("utf-8")) > TITLE_BYTES - 4
    assert len(hit.excerpt.text.encode("utf-8")) > EXCERPT_BYTES - _WIDEST_LINE - 1
    assert (
        len(hit.supporting.text.encode("utf-8")) > SUPPORTING_BYTES - _WIDEST_LINE - 1
    )
    for excerpt in (hit.excerpt, hit.supporting):
        headings = excerpt.section.split(" > ")
        assert len(headings) == _DEEPEST_PATH
        assert all(len(h.encode("utf-8")) > SECTION_BYTES - 4 for h in headings)


def worst_case_ranking(shape: str) -> list[SearchHit]:
    """Build a full ranking of worst-case hits of one text *shape*.

    Args:
        shape: A key of :data:`WORST_SHAPES`.

    Returns:
        :data:`~vaultspec_core.search.MAX_RESULTS` hits, each at every cap.
    """
    unit, per_line = WORST_SHAPES[shape]
    ranking = [_worst_case_hit(i, unit, per_line) for i in range(MAX_RESULTS)]
    for hit in ranking:
        _assert_at_every_cap(hit)
    return ranking
