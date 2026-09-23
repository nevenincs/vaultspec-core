"""Tests for fence-aware markdown structure scanning.

Pins the CommonMark fence and ATX-heading rules every scanner shares, and the
excerpt-block contract: blocks are verbatim line slices, headings set the path
rather than joining a block, and the size rules merge and split only at line
boundaries. Expected values are derived by hand from the documents built in
each test. No mocks, patches, or skips.
"""

from __future__ import annotations

import pytest

from vaultspec_core.vaultcore.markdown import (
    HTML_COMMENT_RE,
    INLINE_CODE_RE,
    Block,
    Heading,
    LineRole,
    document_title,
    find_section,
    iter_headings,
    iter_sections,
    line_roles,
    non_prose_spans,
    paragraph_blocks,
    parse_atx_heading,
)

pytestmark = [pytest.mark.unit]

TEXT = LineRole.TEXT
OPEN = LineRole.FENCE_OPEN
CODE = LineRole.CODE
CLOSE = LineRole.FENCE_CLOSE


def _slice(text: str, block: Block) -> str:
    return "\n".join(text.split("\n")[block.line_start - 1 : block.line_end])


class TestFences:
    def test_backtick_fence_opens_and_closes(self) -> None:
        lines = ["prose", "```py", "x = 1", "```", "after"]
        assert line_roles(lines) == [TEXT, OPEN, CODE, CLOSE, TEXT]

    def test_other_character_does_not_close(self) -> None:
        assert line_roles(["~~~", "```", "~~~"]) == [OPEN, CODE, CLOSE]
        assert line_roles(["```", "~~~", "```"]) == [OPEN, CODE, CLOSE]

    def test_closer_must_be_at_least_as_long(self) -> None:
        lines = ["````", "```", "`````", "after"]
        assert line_roles(lines) == [OPEN, CODE, CLOSE, TEXT]

    def test_closer_with_info_string_does_not_close(self) -> None:
        assert line_roles(["```", "```py", "```"]) == [OPEN, CODE, CLOSE]

    def test_closer_may_carry_trailing_whitespace(self) -> None:
        assert line_roles(["```", "x", "```  \t", "after"]) == [
            OPEN,
            CODE,
            CLOSE,
            TEXT,
        ]

    def test_indentation_limit_is_three_spaces(self) -> None:
        assert line_roles(["   ```", "x", "   ```"]) == [OPEN, CODE, CLOSE]
        assert line_roles(["    ```", "x"]) == [TEXT, TEXT]
        # A four-space-indented run inside a fence is content, not a closer.
        assert line_roles(["```", "    ```", "```"]) == [OPEN, CODE, CLOSE]

    def test_fence_nested_in_a_list_item_is_measured_from_its_content(
        self,
    ) -> None:
        lines = [
            "1. Outer",
            "   - Inner",
            "",
            "     ```bash",
            "     echo  ",
            "",
            "     ```",
            "   after",
        ]
        assert line_roles(lines) == [TEXT, TEXT, TEXT, OPEN, CODE, CODE, CLOSE, TEXT]

    def test_fence_follows_list_nesting_to_any_depth(self) -> None:
        lines = ["- a", "  - b", "    - c", "      ~~~", "      x", "      ~~~"]
        assert line_roles(lines) == [TEXT, TEXT, TEXT, OPEN, CODE, CLOSE]

    def test_blank_lines_keep_a_list_item_open(self) -> None:
        lines = ["- item", "", "", "    ```", "    x", "    ```"]
        assert line_roles(lines) == [TEXT, TEXT, TEXT, OPEN, CODE, CLOSE]

    def test_indented_code_inside_a_list_item_is_not_a_fence(self) -> None:
        # Four spaces past the item's content column is indented code.
        assert line_roles(["- item", "", "      ```", "      x"]) == [TEXT] * 4

    def test_a_line_at_the_margin_closes_the_list_item(self) -> None:
        lines = ["- item", "prose at the margin", "    ```", "    x"]
        assert line_roles(lines) == [TEXT] * 4

    def test_a_list_marker_needs_whitespace_after_it(self) -> None:
        assert line_roles(["-item", "    ```", "1.5 GHz", "    ```"]) == [TEXT] * 4

    def test_a_list_fence_closes_at_or_left_of_its_margin(self) -> None:
        # The closer may sit anywhere from the margin to three spaces past
        # the column the fence opened at; four past is content.
        assert line_roles(["- item", "    ```", "x", "```"]) == [
            TEXT,
            OPEN,
            CODE,
            CLOSE,
        ]
        assert line_roles(["- item", "  ```", "      ```", "     ```"]) == [
            TEXT,
            OPEN,
            CODE,
            CLOSE,
        ]

    def test_lines_inside_a_fence_open_no_list_item(self) -> None:
        lines = ["```", "- item", "```", "    ```", "x"]
        assert line_roles(lines) == [OPEN, CODE, CLOSE, TEXT, TEXT]

    def test_backtick_info_string_may_not_contain_a_backtick(self) -> None:
        assert line_roles(["``` a`b", "x"]) == [TEXT, TEXT]
        assert line_roles(["~~~ a`b", "x"]) == [OPEN, CODE]

    def test_runs_shorter_than_three_are_not_fences(self) -> None:
        assert line_roles(["``", "~~", "x"]) == [TEXT, TEXT, TEXT]

    def test_unclosed_fence_runs_to_end(self) -> None:
        assert line_roles(["```", "x", "# heading", ""]) == [OPEN, CODE, CODE, CODE]

    def test_crlf_line_endings_are_whitespace(self) -> None:
        assert line_roles(["```\r", "x\r", "```\r", "y"]) == [OPEN, CODE, CLOSE, TEXT]

    def test_lines_with_newlines_attached_classify_the_same(self) -> None:
        assert line_roles(["```\n", "x\n", "```\n"]) == [OPEN, CODE, CLOSE]

    def test_fenced_covers_delimiters_and_content(self) -> None:
        assert [role.fenced for role in LineRole] == [False, True, True, True]


class TestHeadings:
    @pytest.mark.parametrize(
        ("line", "expected"),
        [
            ("# Title", (1, "Title")),
            ("###### Six", (6, "Six")),
            ("#\tTabbed", (1, "Tabbed")),
            ("   ## Indented three", (2, "Indented three")),
            ("## Closing ##", (2, "Closing")),
            ("## Closing ##   ", (2, "Closing")),
            ("## C#", (2, "C#")),
            ("## Escaped \\#", (2, "Escaped \\#")),
            ("### ###", (3, "")),
            ("#", (1, "")),
            ("## Windows\r", (2, "Windows")),
            (
                "# `demo` adr: `Title` | (**status:** `accepted`)",
                (1, "`demo` adr: `Title` | (**status:** `accepted`)"),
            ),
        ],
    )
    def test_parse_atx_heading(self, line: str, expected: tuple[int, str]) -> None:
        assert parse_atx_heading(line) == expected

    @pytest.mark.parametrize(
        "line",
        ["####### Seven", "#hashtag", "    # Indented four", "text # not", ""],
    )
    def test_not_a_heading(self, line: str) -> None:
        assert parse_atx_heading(line) is None

    def test_headings_inside_fences_are_ignored(self) -> None:
        text = (
            "# Doc\n"
            "```bash\n"
            "# ===== banner\n"
            "```\n"
            "~~~~\n"
            "## Quoted\n"
            "~~~\n"
            "~~~~\n"
            "## Real ##\n"
        )
        assert list(iter_headings(text)) == [
            Heading(level=1, text="Doc", line=1),
            Heading(level=2, text="Real", line=9),
        ]

    def test_document_title_skips_fenced_and_empty_h1(self) -> None:
        text = "```md\n# Sample\n```\n#\n\n# Real Title #\n\n# Second\n"
        assert document_title(text) == "Real Title"

    def test_document_title_absent(self) -> None:
        assert document_title("## Only a section\n\nProse.\n") is None


_DOCUMENT = """# Environment variables

Lead paragraph one.
Lead continues.

## Decision

Use a registry.

```bash
# ===== section banner
export A=1

# ===== another banner
export B=2
```

### Details

Detail text.

## Consequences ##

Final words.
"""


class TestParagraphBlocks:
    def test_structure_without_merging(self) -> None:
        blocks = paragraph_blocks(_DOCUMENT, min_chars=0)
        assert [(b.heading_path, b.line_start, b.line_end) for b in blocks] == [
            ((), 3, 4),
            (("Decision",), 8, 8),
            (("Decision",), 10, 16),
            (("Decision", "Details"), 20, 20),
            (("Consequences",), 24, 24),
        ]
        fence = blocks[2].text
        assert fence.startswith("```bash\n# ===== section banner")
        assert "export A=1\n\n# ===== another banner" in fence
        assert fence.endswith("export B=2\n```")

    def test_small_blocks_merge_only_without_a_heading_between(self) -> None:
        blocks = paragraph_blocks(_DOCUMENT, min_chars=50)
        # "Use a registry." (15 chars) absorbs the fence after it; the lead
        # paragraph (35 chars) is followed by a heading and stays alone.
        assert [(b.line_start, b.line_end) for b in blocks] == [
            (3, 4),
            (8, 16),
            (20, 20),
            (24, 24),
        ]
        assert blocks[1].text.startswith("Use a registry.\n\n```bash")

    @pytest.mark.parametrize(
        ("max_chars", "min_chars"), [(1400, 240), (40, 0), (20, 30)]
    )
    def test_every_block_is_a_verbatim_slice(
        self, max_chars: int, min_chars: int
    ) -> None:
        for text in (_DOCUMENT, _DOCUMENT.replace("\n", "\r\n")):
            blocks = paragraph_blocks(text, max_chars=max_chars, min_chars=min_chars)
            assert blocks
            for block in blocks:
                assert block.text == _slice(text, block)
                assert block.text.strip()

    def test_merge_stops_once_minimum_is_reached(self) -> None:
        text = "xxxxxx\n\nyyyyyy\n\nzzzzzz"
        blocks = paragraph_blocks(text, min_chars=10)
        assert [(b.line_start, b.line_end) for b in blocks] == [(1, 3), (5, 5)]
        assert blocks[0].text == "xxxxxx\n\nyyyyyy"

    def test_merge_never_exceeds_maximum(self) -> None:
        text = "xxxxxx\n\nyyyyyy\n\nzzzzzz"
        blocks = paragraph_blocks(text, max_chars=12, min_chars=10)
        assert [(b.line_start, b.line_end) for b in blocks] == [(1, 1), (3, 3), (5, 5)]

    def test_same_path_behind_a_heading_does_not_merge(self) -> None:
        text = "## A\n\nshort\n\n## A\n\nshort again\n"
        blocks = paragraph_blocks(text, min_chars=100)
        assert [(b.heading_path, b.line_start, b.line_end) for b in blocks] == [
            (("A",), 3, 3),
            (("A",), 7, 7),
        ]

    def test_oversized_block_splits_at_line_boundaries(self) -> None:
        text = "aaaa\nbbbb\ncccc\ndddd"
        blocks = paragraph_blocks(text, max_chars=10, min_chars=0)
        assert [b.text for b in blocks] == ["aaaa\nbbbb", "cccc\ndddd"]
        assert [(b.line_start, b.line_end) for b in blocks] == [(1, 2), (3, 4)]

    def test_line_longer_than_maximum_stays_whole(self) -> None:
        long_line = "x" * 25
        text = f"aa\n{long_line}\nbb"
        blocks = paragraph_blocks(text, max_chars=10, min_chars=5)
        assert [b.text for b in blocks] == ["aa", long_line, "bb"]

    def test_heading_path_nests_and_resets(self) -> None:
        text = (
            "## A\n### B\n#### C\nunder c\n### D\nunder d\n"
            "# Another title\nafter title\n## E ##\nunder e"
        )
        blocks = paragraph_blocks(text, min_chars=0)
        assert [(b.heading_path, b.text) for b in blocks] == [
            (("A", "B", "C"), "under c"),
            (("A", "D"), "under d"),
            ((), "after title"),
            (("E",), "under e"),
        ]

    def test_unclosed_fence_swallows_headings_to_the_end(self) -> None:
        text = "## H\n```\ncode\n\n## not a heading\n\n"
        assert paragraph_blocks(text, min_chars=0) == [
            Block(
                heading_path=("H",),
                line_start=2,
                line_end=5,
                text="```\ncode\n\n## not a heading",
            )
        ]

    def test_fence_nested_in_a_list_item_stays_whole(self) -> None:
        text = "- item\n\n    ```\n    a\n\n    b\n    ```\n"
        blocks = paragraph_blocks(text, min_chars=0)
        assert [(b.line_start, b.line_end) for b in blocks] == [(1, 1), (3, 7)]

    def test_blank_text_has_no_blocks(self) -> None:
        assert paragraph_blocks("") == []
        assert paragraph_blocks("\n  \n\t\n# Title only\n") == []

    def test_non_positive_maximum_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="max_chars"):
            paragraph_blocks("text", max_chars=0)


_SECTIONED = (
    "# T\n\n## A\n\nalpha\n### A1\nsub\n## Wave `W01` - w\nwave text\n"
    "```\n## Fenced\n```\n## B\nbeta"
)


class TestSections:
    def test_sections_run_to_the_next_opening_heading(self) -> None:
        sections = list(iter_sections(_SECTIONED))
        assert [s.heading.text for s in sections] == ["A", "Wave `W01` - w", "B"]
        assert sections[0].body == "\nalpha\n### A1\nsub\n"
        assert sections[1].body == "wave text\n```\n## Fenced\n```\n"
        assert sections[2].body == "beta"
        for section in sections:
            assert _SECTIONED[section.start : section.end] == section.body

    def test_a_heading_that_does_not_open_extends_the_section_before_it(
        self,
    ) -> None:
        sections = list(
            iter_sections(_SECTIONED, opens=lambda h: not h.text.startswith("Wave"))
        )
        assert [s.heading.text for s in sections] == ["A", "B"]
        assert sections[0].body == (
            "\nalpha\n### A1\nsub\n## Wave `W01` - w\nwave text\n```\n## Fenced\n```\n"
        )

    def test_find_section_by_title_and_level(self) -> None:
        assert find_section(_SECTIONED, "B") is not None
        assert find_section(_SECTIONED, "Fenced") is None
        sub = find_section(_SECTIONED, "A1", level=3)
        assert sub is not None
        # Headings of other levels neither open nor end a level-three section.
        assert sub.body == (
            "sub\n## Wave `W01` - w\nwave text\n```\n## Fenced\n```\n## B\nbeta"
        )

    def test_heading_on_the_last_line_has_an_empty_body(self) -> None:
        section = find_section("text\n## Only", "Only")
        assert section is not None
        assert (section.start, section.end, section.body) == (12, 12, "")


def _pieces(text: str) -> list[str]:
    return [text[start:end] for start, end in non_prose_spans(text)]


class TestNonProseSpans:
    def test_inline_code_and_comments(self) -> None:
        assert _pieces("a `x` b <!-- c --> d") == ["`x`", "<!-- c -->"]

    def test_fence_marker_inside_a_comment_opens_nothing(self) -> None:
        assert _pieces("<!--\n```\n-->\ntext\n") == ["<!--\n```\n-->"]

    def test_comment_marker_inside_inline_code_opens_nothing(self) -> None:
        text = "see `<!--` here\n```\ncode\n```\nafter"
        assert _pieces(text) == ["`<!--`", "```\ncode\n```"]

    def test_unclosed_fence_runs_to_the_end(self) -> None:
        assert _pieces("x\n```\ncode") == ["```\ncode"]

    def test_fence_wins_over_inline_code_at_the_same_position(self) -> None:
        assert _pieces("```\n`a`\n```") == ["```\n`a`\n```"]

    def test_fence_nested_in_a_list_item_hides_its_content(self) -> None:
        text = "- see `x`\n\n    ```\n    [[not-a-link]]\n    ```\n- `y`\n"
        assert _pieces(text) == [
            "`x`",
            "    ```\n    [[not-a-link]]\n    ```",
            "`y`",
        ]

    def test_list_item_inside_a_comment_sets_no_margin(self) -> None:
        text = "<!--\n- item\n-->\n    ~~~\n    code\n"
        assert _pieces(text) == ["<!--\n- item\n-->"]

    def test_comment_forms(self) -> None:
        text = "<!-->a<!--->b<!-- c -->"
        assert HTML_COMMENT_RE.findall(text) == ["<!-->", "<!--->", "<!-- c -->"]

    def test_double_backtick_span_may_quote_a_backtick(self) -> None:
        match = INLINE_CODE_RE.search("x ``a`b`` y")
        assert match is not None
        assert match.group(0) == "``a`b``"
