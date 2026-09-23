"""The search corpus over real vault records written to disk."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vaultspec_core.search._corpus import (
    CARD_SECTIONS,
    LEAD_CHARS,
    SEARCHABLE_TYPES,
    SECTION_CHARS,
    blob_hash,
    card_title,
    load_records,
    readable,
    record_blocks,
    summary_card,
    template_headings,
)
from vaultspec_core.vaultcore.blob_hash import git_blob_oid
from vaultspec_core.vaultcore.body_schema import BODY_SCHEMA_REGISTRY
from vaultspec_core.vaultcore.models import DocType

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]

#: The UTF-8 byte-order mark some editors write first.
BOM = "\N{ZERO WIDTH NO-BREAK SPACE}"


def write_record(
    root: Path,
    doc_type: DocType | str,
    stem: str,
    body: str,
    *,
    feature: str = "demo",
    date: str = "2026-01-02",
    newline: str = "\n",
    bom: bool = False,
) -> Path:
    """Write one vault record with real frontmatter under ``root/.vault``.

    Args:
        root: The workspace root.
        doc_type: The record type, which names its directory.
        stem: The file stem.
        body: The markdown body, with ``\\n`` line endings.
        feature: The feature tag, without ``#``.
        date: The frontmatter date.
        newline: The line ending written to disk.
        bom: Whether the file starts with a UTF-8 byte-order mark.

    Returns:
        The written path.
    """
    kind = DocType(doc_type).value
    frontmatter = (
        f"---\ntags:\n  - '#{kind}'\n  - '#{feature}'\ndate: '{date}'\n"
        "related: []\n---\n\n"
    )
    text = (frontmatter + body).replace("\n", newline)
    path = root / ".vault" / kind / f"{stem}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((BOM if bom else "").encode() + text.encode("utf-8"))
    return path


def file_lines(path: Path, start: int, end: int) -> str:
    """Return the file's lines *start* through *end*, as a reader sees them."""
    lines = path.read_text(encoding="utf-8").split("\n")
    return "\n".join(lines[start - 1 : end])


ADR_BODY = """\
# `cache` adr: `graph cache` | (**status:** `accepted`)

| field | value |
| ----- | ----- |

```text
a fenced sample comes before the prose
```

The graph cache is keyed by a **content fingerprint** so a stale read is
impossible after an edit.

## Problem Statement

Rebuilding the graph on every command costs seconds.

## Constraints

- The cache must never serve stale data.

## Cache layout on disk

### Fingerprint manifest

The manifest lists every file with its size and mtime.

#### Too deep for a card

Detail.
"""


class TestLoadRecords:
    def test_reads_every_searchable_record_with_its_metadata(
        self, tmp_path: Path
    ) -> None:
        write_record(tmp_path, "adr", "2026-01-02-cache-adr", ADR_BODY, feature="cache")
        write_record(tmp_path, "research", "2026-01-02-cache-research", "# r\n\nx\n")

        records = load_records(tmp_path)

        assert [r.rel_path for r in records] == [
            ".vault/adr/2026-01-02-cache-adr.md",
            ".vault/research/2026-01-02-cache-research.md",
        ]
        adr = records[0]
        assert adr.name == "2026-01-02-cache-adr"
        assert adr.doc_type is DocType.ADR
        assert adr.feature == "cache"
        assert adr.date == "2026-01-02"
        assert adr.title == "`cache` adr: `graph cache` | (**status:** `accepted`)"
        assert adr.body.startswith("# `cache` adr")
        assert adr.path == tmp_path / ".vault" / "adr" / "2026-01-02-cache-adr.md"

    def test_generated_indexes_are_never_records(self, tmp_path: Path) -> None:
        write_record(tmp_path, "index", "demo.index", "# index\n\n- a\n")
        write_record(tmp_path, "plan", "2026-01-02-demo-plan", "# plan\n\nx\n")

        records = load_records(tmp_path)

        assert [r.doc_type for r in records] == [DocType.PLAN]
        assert DocType.INDEX not in SEARCHABLE_TYPES

    def test_filters_by_type_feature_and_date(self, tmp_path: Path) -> None:
        write_record(tmp_path, "adr", "2026-01-02-a-adr", "# a\n\nx\n", feature="a")
        write_record(
            tmp_path, "adr", "2026-01-03-b-adr", "# b\n", feature="b", date="2026-01-03"
        )
        write_record(tmp_path, "audit", "2026-01-02-a-audit", "# c\n", feature="a")

        by_type = load_records(tmp_path, doc_types=[DocType.AUDIT])
        by_feature = load_records(tmp_path, feature="#a")
        by_date = load_records(tmp_path, date="2026-01-03")
        none_left = load_records(tmp_path, doc_types=[DocType.INDEX])

        assert [r.name for r in by_type] == ["2026-01-02-a-audit"]
        assert [r.name for r in by_feature] == [
            "2026-01-02-a-adr",
            "2026-01-02-a-audit",
        ]
        assert [r.name for r in by_date] == ["2026-01-03-b-adr"]
        assert none_left == []

    def test_untitled_record_is_titled_by_its_stem(self, tmp_path: Path) -> None:
        write_record(tmp_path, "exec", "2026-01-02-demo-ledger", "Rows only.\n")

        (record,) = load_records(tmp_path)

        assert record.title == "2026-01-02-demo-ledger"

    def test_undecodable_file_is_skipped(self, tmp_path: Path) -> None:
        path = write_record(tmp_path, "adr", "2026-01-02-bad-adr", "# ok\n")
        path.write_bytes(b"---\ntags:\n  - '#adr'\n---\n# \xff\xfe broken\n")
        write_record(tmp_path, "adr", "2026-01-02-good-adr", "# good\n")

        assert [r.name for r in load_records(tmp_path)] == ["2026-01-02-good-adr"]


class TestBlocks:
    @pytest.mark.parametrize(
        ("newline", "bom"), [("\n", False), ("\r\n", False), ("\n", True)]
    )
    def test_block_line_ranges_address_the_file(
        self, tmp_path: Path, newline: str, bom: bool
    ) -> None:
        path = write_record(
            tmp_path, "adr", "2026-01-02-cache-adr", ADR_BODY, newline=newline, bom=bom
        )

        (record,) = load_records(tmp_path)
        blocks = record_blocks(record)

        assert blocks
        for block in blocks:
            assert block.text == file_lines(path, block.line_start, block.line_end)

    def test_body_starts_after_the_frontmatter(self, tmp_path: Path) -> None:
        write_record(tmp_path, "adr", "2026-01-02-cache-adr", ADR_BODY)

        (record,) = load_records(tmp_path)

        # Seven frontmatter lines and one blank line precede the title.
        assert record.body_line == 9
        first = record_blocks(record)[0]
        assert first.line_start == 11
        assert first.text.startswith("| field |")

    def test_blocks_carry_their_heading_path(self, tmp_path: Path) -> None:
        write_record(tmp_path, "adr", "2026-01-02-cache-adr", ADR_BODY)

        (record,) = load_records(tmp_path)
        paths = {block.heading_path for block in record_blocks(record)}

        assert ("Cache layout on disk", "Fingerprint manifest") in paths

    def test_empty_body_has_no_blocks(self, tmp_path: Path) -> None:
        write_record(tmp_path, "plan", "2026-01-02-demo-plan", "")

        (record,) = load_records(tmp_path)

        assert record_blocks(record) == []


class TestCards:
    def test_card_title_is_readable(self, tmp_path: Path) -> None:
        write_record(tmp_path, "adr", "2026-01-02-cache-adr", ADR_BODY)

        (record,) = load_records(tmp_path)

        assert card_title(record) == "cache adr: graph cache | (status: accepted)"

    def test_lead_is_the_first_prose_paragraph(self, tmp_path: Path) -> None:
        write_record(tmp_path, "adr", "2026-01-02-cache-adr", ADR_BODY)

        (record,) = load_records(tmp_path)

        assert summary_card(record)["lead"] == (
            "The graph cache is keyed by a content fingerprint so a stale read is "
            "impossible after an edit."
        )

    def test_lead_is_bounded(self, tmp_path: Path) -> None:
        write_record(
            tmp_path, "research", "2026-01-02-r-research", "# r\n\n" + "w " * 400
        )

        (record,) = load_records(tmp_path)
        lead = summary_card(record)["lead"]

        assert isinstance(lead, str)
        assert len(lead) == LEAD_CHARS

    def test_sections_skip_the_type_template_and_deep_headings(
        self, tmp_path: Path
    ) -> None:
        write_record(tmp_path, "adr", "2026-01-02-cache-adr", ADR_BODY)

        (record,) = load_records(tmp_path)

        assert summary_card(record)["sections"] == [
            "Cache layout on disk",
            "Fingerprint manifest",
        ]

    def test_sections_are_bounded_in_count_and_length(self, tmp_path: Path) -> None:
        headings = "".join(f"## Topic {i} {'x' * 120}\n\ntext\n\n" for i in range(15))
        write_record(
            tmp_path, "research", "2026-01-02-r-research", "# r\n\n" + headings
        )

        (record,) = load_records(tmp_path)

        assert summary_card(record)["sections"] == [
            f"Topic {i} {'x' * 120}"[:SECTION_CHARS] for i in range(CARD_SECTIONS)
        ]

    def test_card_without_prose_or_sections_is_just_the_title(
        self, tmp_path: Path
    ) -> None:
        write_record(
            tmp_path, "exec", "2026-01-02-demo-ledger", "# ledger\n\n## Changes\n"
        )

        (record,) = load_records(tmp_path)

        assert summary_card(record) == {"title": "ledger"}

    def test_readable_collapses_markup_and_whitespace(self) -> None:
        assert readable("  **bold** and `code`\n  wrapped  ") == "bold and code wrapped"


class TestTemplateHeadings:
    def test_template_comes_from_every_schema_version_of_the_type(self) -> None:
        expected = {
            title
            for schema in BODY_SCHEMA_REGISTRY.values()
            for (doc_type, _), titles in schema.sections.items()
            if doc_type is DocType.ADR
            for title in titles
        }

        assert template_headings(DocType.ADR) == expected
        assert {"Constraints", "Codification candidates"} <= expected

    def test_template_is_per_type(self) -> None:
        assert "Changes" in template_headings(DocType.EXEC)
        assert "Changes" not in template_headings(DocType.ADR)


class TestBlobHash:
    def test_hash_is_the_git_blob_id_of_the_file_on_disk(self, tmp_path: Path) -> None:
        path = write_record(tmp_path, "adr", "2026-01-02-cache-adr", ADR_BODY)
        (record,) = load_records(tmp_path)

        before = blob_hash(record)
        path.write_bytes(path.read_bytes() + b"\nappended\n")
        after = blob_hash(record)

        assert after == git_blob_oid(path.read_bytes())
        assert before is not None
        assert before != after

    def test_missing_file_has_no_hash(self, tmp_path: Path) -> None:
        path = write_record(tmp_path, "adr", "2026-01-02-cache-adr", ADR_BODY)
        (record,) = load_records(tmp_path)

        path.unlink()

        assert blob_hash(record) is None
