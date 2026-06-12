"""Tests for the ``modified_stamp_backfill`` migration (0.1.29).

Exercises
:func:`vaultspec_core.migrations.m_0_1_29_modified_stamp_backfill.migrate`
against real on-disk fixtures. The migration inserts a canonical
``modified:`` stamp into every document that lacks one, derived from the
leniently-parsed ``date:`` field or the filename ``yyyy-mm-dd`` prefix,
and is a true no-op on documents that already carry the field.

Covers backfill, idempotence (a second run mutates nothing), lenient
date handling, the filename-prefix fallback, and the skip path. All
fixtures are real files; no mocks, patches, or skips.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vaultspec_core.config import reset_config
from vaultspec_core.migrations.m_0_1_29_modified_stamp_backfill import migrate
from vaultspec_core.vaultcore import parse_vault_metadata

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

pytestmark = [pytest.mark.unit]


@pytest.fixture(autouse=True)
def _reset_cfg() -> Generator[None]:
    reset_config()
    yield
    reset_config()


def _skeleton(root: Path) -> None:
    for sub in ("adr", "audit", "exec", "plan", "reference", "research"):
        (root / ".vault" / sub).mkdir(parents=True, exist_ok=True)


def _write_doc(
    root: Path,
    stem: str,
    *,
    feature: str = "feat",
    date_line: str | None = "date: '2026-02-08'",
    modified_line: str | None = None,
    sub: str = "adr",
    tag: str = "#adr",
) -> Path:
    """Write a minimal vault document and return its path."""
    lines = ["---", "tags:", f"  - '{tag}'", f"  - '#{feature}'"]
    if date_line is not None:
        lines.append(date_line)
    if modified_line is not None:
        lines.append(modified_line)
    lines += ["---", "", f"# {stem}", ""]
    doc = root / ".vault" / sub / f"{stem}.md"
    doc.write_text("\n".join(lines), encoding="utf-8")
    return doc


def _modified(doc: Path) -> str | None:
    meta, _ = parse_vault_metadata(doc.read_text(encoding="utf-8"))
    return meta.modified


class TestBackfill:
    def test_backfills_from_date(self, tmp_path: Path):
        _skeleton(tmp_path)
        doc = _write_doc(
            tmp_path, "2026-02-08-alpha-adr", date_line="date: '2026-02-08'"
        )

        result = migrate(tmp_path)

        assert result.target_version == "0.1.29"
        assert result.counts["backfilled"] == 1
        assert _modified(doc) == "2026-02-08"
        assert "backfilled modified stamp on 1 document" in result.summary

    def test_lenient_date_is_canonicalized(self, tmp_path: Path):
        # An unquoted slash date is parsed leniently and stamped in
        # canonical yyyy-mm-dd form.
        _skeleton(tmp_path)
        doc = _write_doc(tmp_path, "2026-02-08-alpha-adr", date_line="date: 2026/02/08")

        result = migrate(tmp_path)

        assert result.counts["backfilled"] == 1
        assert _modified(doc) == "2026-02-08"

    def test_filename_prefix_fallback(self, tmp_path: Path):
        # date: is present but unparseable, so the stamp value comes from
        # the filename prefix while the date: line anchors the insertion.
        _skeleton(tmp_path)
        doc = _write_doc(
            tmp_path,
            "2026-03-15-beta-adr",
            date_line="date: 'garbage'",
        )

        result = migrate(tmp_path)

        assert result.counts["backfilled"] == 1
        assert _modified(doc) == "2026-03-15"

    def test_backfills_multiple_documents(self, tmp_path: Path):
        _skeleton(tmp_path)
        for i in range(5):
            _write_doc(
                tmp_path,
                f"2026-02-0{i + 1}-doc-{i}-adr",
                date_line=f"date: '2026-02-0{i + 1}'",
            )

        result = migrate(tmp_path)

        assert result.counts["backfilled"] == 5


class TestIdempotence:
    def test_already_stamped_is_untouched(self, tmp_path: Path):
        _skeleton(tmp_path)
        doc = _write_doc(
            tmp_path,
            "2026-02-08-alpha-adr",
            date_line="date: '2026-02-08'",
            modified_line="modified: '2026-02-08'",
        )
        before = doc.read_text(encoding="utf-8")

        result = migrate(tmp_path)

        assert doc.read_text(encoding="utf-8") == before
        assert result.counts["backfilled"] == 0
        assert result.counts["already"] == 1

    def test_noncanonical_existing_value_left_untouched(self, tmp_path: Path):
        # The backfill never normalizes an existing stamp; that is the
        # reconciliation checker's job. A non-canonical existing value is
        # counted as already-present and not rewritten.
        _skeleton(tmp_path)
        doc = _write_doc(
            tmp_path,
            "2026-02-08-alpha-adr",
            date_line="date: '2026-02-08'",
            modified_line="modified: '2026/02/08'",
        )
        before = doc.read_text(encoding="utf-8")

        result = migrate(tmp_path)

        assert doc.read_text(encoding="utf-8") == before
        assert result.counts["already"] == 1

    def test_second_run_is_noop(self, tmp_path: Path):
        _skeleton(tmp_path)
        doc = _write_doc(
            tmp_path, "2026-02-08-alpha-adr", date_line="date: '2026-02-08'"
        )

        first = migrate(tmp_path)
        assert first.counts["backfilled"] == 1
        after_first = doc.read_text(encoding="utf-8")

        second = migrate(tmp_path)
        assert second.counts["backfilled"] == 0
        assert second.counts["already"] == 1
        assert doc.read_text(encoding="utf-8") == after_first


class TestSkipPath:
    def test_no_date_and_no_filename_prefix_is_skipped(self, tmp_path: Path):
        _skeleton(tmp_path)
        doc = _write_doc(
            tmp_path,
            "undated-note-adr",
            date_line=None,
        )

        result = migrate(tmp_path)

        assert result.counts["skipped"] == 1
        assert result.counts["backfilled"] == 0
        assert _modified(doc) is None
        assert "skipped" in result.summary

    def test_filename_date_without_anchor_is_skipped(self, tmp_path: Path):
        # The filename carries a date but there is no date: anchor to
        # insert the stamp after, so the document is skipped rather than
        # claiming a backfill that did not happen.
        _skeleton(tmp_path)
        doc = _write_doc(
            tmp_path,
            "2026-03-15-anchorless-adr",
            date_line=None,
        )

        result = migrate(tmp_path)

        assert result.counts["skipped"] == 1
        assert _modified(doc) is None


class TestNoVault:
    def test_missing_docs_dir_is_noop(self, tmp_path: Path):
        result = migrate(tmp_path)
        assert result.counts["backfilled"] == 0
        assert "no .vault" in result.summary
