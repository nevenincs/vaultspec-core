"""Tests for the ``modified-stamp`` vault health checker.

Exercises every semantic of
:func:`~vaultspec_core.vaultcore.checks.modified_stamp.check_modified_stamp`
against real on-disk documents (vault-orientation ADR decisions D3, D3b):

- a missing stamp is flagged and, under fix, backfilled from ``date:``
  or the filename ``yyyy-mm-dd`` prefix;
- a present-but-non-canonical yet parseable stamp is flagged and
  normalized to the canonical quoted form, preserving the parsed value;
- an unparseable stamp is flagged as an error and never rewritten;
- a stale stamp (file mtime newer than the stamp) is flagged and
  refreshed under fix;
- the git-operation signature - a fresh clone (one mtime instant) or a
  pre-commit stash/restore cycle (two) - suppresses staleness findings
  and emits a single informational diagnostic.

All fixtures are real files; mtimes are set with :func:`os.utime`. No
mocks, patches, or skips.
"""

from __future__ import annotations

import datetime
import os
from typing import TYPE_CHECKING

import pytest

from ....config import reset_config
from ....graph import VaultGraph
from .._base import Severity
from ..modified_stamp import check_modified_stamp

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
    """Write a minimal vault document and return its path.

    Args:
        root: Vault root.
        stem: Filename stem (without ``.md``).
        feature: Feature tag value (without ``#``).
        date_line: Full ``date:`` frontmatter line, or ``None`` to omit.
        modified_line: Full ``modified:`` frontmatter line, or ``None``.
        sub: ``.vault`` subdirectory.
        tag: Directory tag for the document.

    Returns:
        The written document path.
    """
    lines = ["---", "tags:", f"  - '{tag}'", f"  - '#{feature}'"]
    if date_line is not None:
        lines.append(date_line)
    if modified_line is not None:
        lines.append(modified_line)
    lines += ["---", "", f"# {stem}", ""]
    doc = root / ".vault" / sub / f"{stem}.md"
    doc.write_text("\n".join(lines), encoding="utf-8")
    return doc


def _set_mtime(path: Path, date: datetime.date) -> None:
    """Set a file's mtime to noon on *date* (local time)."""
    ts = datetime.datetime(date.year, date.month, date.day, 12, 0, 0).timestamp()
    os.utime(path, (ts, ts))


def _uniform_mtime(root: Path, date: datetime.date) -> None:
    """Set every vault document's mtime to *date* (the clone signature)."""
    for doc in (root / ".vault").rglob("*.md"):
        _set_mtime(doc, date)


def _check(root: Path, *, fix: bool = False):
    graph = VaultGraph(root)
    return check_modified_stamp(root, snapshot=graph.to_snapshot(), fix=fix)


class TestMissingStamp:
    def test_missing_is_flagged(self, tmp_path: Path):
        _skeleton(tmp_path)
        _write_doc(tmp_path, "2026-02-08-alpha-adr")
        _uniform_mtime(tmp_path, datetime.date(2026, 2, 8))

        result = _check(tmp_path)

        warnings = [d for d in result.diagnostics if d.severity == Severity.WARNING]
        assert len(warnings) == 1
        assert "Missing modified stamp" in warnings[0].message
        assert warnings[0].fixable is True

    def test_fix_backfills_from_date(self, tmp_path: Path):
        _skeleton(tmp_path)
        doc = _write_doc(
            tmp_path, "2026-02-08-alpha-adr", date_line="date: '2026-02-08'"
        )
        _uniform_mtime(tmp_path, datetime.date(2026, 2, 8))

        result = _check(tmp_path, fix=True)

        assert result.fixed_count == 1
        assert "modified: '2026-02-08'" in doc.read_text(encoding="utf-8")

    def test_fix_backfills_from_filename_when_date_absent(self, tmp_path: Path):
        _skeleton(tmp_path)
        doc = _write_doc(
            tmp_path,
            "2026-03-15-beta-adr",
            date_line=None,
        )
        _uniform_mtime(tmp_path, datetime.date(2026, 3, 15))

        result = _check(tmp_path, fix=True)

        # No date: anchor, so the stamp cannot be written even though a
        # filename date exists: the finding survives, reported unfixed.
        text = doc.read_text(encoding="utf-8")
        assert "modified:" not in text
        warnings = [d for d in result.diagnostics if d.severity == Severity.WARNING]
        assert len(warnings) == 1
        assert "Missing modified stamp" in warnings[0].message

    def test_fix_backfills_from_filename_with_date_anchor(self, tmp_path: Path):
        # date: present but unparseable, so the backfill value comes from
        # the filename prefix while the date: line still anchors insertion.
        _skeleton(tmp_path)
        doc = _write_doc(
            tmp_path,
            "2026-03-15-beta-adr",
            date_line="date: 'not-a-date'",
        )
        _uniform_mtime(tmp_path, datetime.date(2026, 3, 15))

        result = _check(tmp_path, fix=True)

        assert result.fixed_count == 1
        assert "modified: '2026-03-15'" in doc.read_text(encoding="utf-8")


class TestNonCanonical:
    def test_iso_timestamp_is_flagged_and_normalized(self, tmp_path: Path):
        _skeleton(tmp_path)
        doc = _write_doc(
            tmp_path,
            "2026-02-08-alpha-adr",
            modified_line="modified: '2026-02-08T09:30:00'",
        )
        _uniform_mtime(tmp_path, datetime.date(2026, 2, 8))

        read_only = _check(tmp_path)
        warnings = [d for d in read_only.diagnostics if d.severity == Severity.WARNING]
        assert len(warnings) == 1
        assert "Non-canonical" in warnings[0].message

        fixed = _check(tmp_path, fix=True)
        assert fixed.fixed_count == 1
        assert "modified: '2026-02-08'" in doc.read_text(encoding="utf-8")

    def test_slash_date_is_normalized_preserving_value(self, tmp_path: Path):
        _skeleton(tmp_path)
        doc = _write_doc(
            tmp_path,
            "2026-02-08-alpha-adr",
            modified_line="modified: '2026/02/08'",
        )
        _uniform_mtime(tmp_path, datetime.date(2026, 2, 8))

        _check(tmp_path, fix=True)

        # The parsed value is preserved (2026-02-08), not today.
        assert "modified: '2026-02-08'" in doc.read_text(encoding="utf-8")


class TestUnparseable:
    def test_unparseable_is_error_and_not_fixed(self, tmp_path: Path):
        _skeleton(tmp_path)
        doc = _write_doc(
            tmp_path,
            "2026-02-08-alpha-adr",
            modified_line="modified: 'tomorrow-ish'",
        )
        _uniform_mtime(tmp_path, datetime.date(2026, 2, 8))

        result = _check(tmp_path, fix=True)

        errors = [d for d in result.diagnostics if d.severity == Severity.ERROR]
        assert len(errors) == 1
        assert "Unparseable modified stamp 'tomorrow-ish'" in errors[0].message
        assert errors[0].fixable is False
        # The offending value is never dropped or rewritten.
        assert "modified: 'tomorrow-ish'" in doc.read_text(encoding="utf-8")
        assert result.fixed_count == 0


class TestStaleness:
    def _diverse_fresh_fillers(self, tmp_path: Path, count: int = 9) -> None:
        """Write *count* fresh fillers with distinct mtime dates.

        Each filler's stamp equals its own mtime so none read as stale,
        and the spread of distinct mtime dates keeps the dominant date
        well under the clone-signature threshold so staleness checks run.
        """
        for i in range(count):
            day = 1 + i
            stamp = f"2026-03-{day:02d}"
            doc = _write_doc(
                tmp_path,
                f"2026-03-{day:02d}-filler-{i}-adr",
                date_line=f"date: '{stamp}'",
                modified_line=f"modified: '{stamp}'",
            )
            _set_mtime(doc, datetime.date(2026, 3, day))

    def test_stale_stamp_flagged_when_mtime_newer(self, tmp_path: Path):
        _skeleton(tmp_path)
        stale = _write_doc(
            tmp_path,
            "2026-02-08-alpha-adr",
            modified_line="modified: '2026-02-08'",
        )
        _set_mtime(stale, datetime.date(2026, 5, 1))
        self._diverse_fresh_fillers(tmp_path)

        result = _check(tmp_path)

        stale_findings = [d for d in result.diagnostics if "Stale" in d.message]
        assert len(stale_findings) == 1
        assert stale_findings[0].path == stale.relative_to(tmp_path)
        assert "2026-05-01" in stale_findings[0].message

    def test_stale_stamp_refreshed_under_fix(self, tmp_path: Path):
        _skeleton(tmp_path)
        stale = _write_doc(
            tmp_path,
            "2026-02-08-alpha-adr",
            modified_line="modified: '2026-02-08'",
        )
        _set_mtime(stale, datetime.date(2026, 5, 1))
        self._diverse_fresh_fillers(tmp_path)

        result = _check(tmp_path, fix=True)

        assert result.fixed_count == 1
        assert "modified: '2026-05-01'" in stale.read_text(encoding="utf-8")


class TestCloneSignatureGuard:
    def test_uniform_mtime_suppresses_staleness(self, tmp_path: Path):
        _skeleton(tmp_path)
        # All documents share one (recent) mtime date while their stamps
        # are older: without the guard every document would be flagged
        # stale. The guard must suppress all staleness findings.
        for i in range(10):
            _write_doc(
                tmp_path,
                f"2026-02-08-doc-{i}-adr",
                modified_line="modified: '2026-02-08'",
            )
        _uniform_mtime(tmp_path, datetime.date(2026, 6, 1))

        result = _check(tmp_path)

        stale_findings = [d for d in result.diagnostics if "Stale" in d.message]
        assert stale_findings == []

    def test_guard_emits_single_info_diagnostic(self, tmp_path: Path):
        _skeleton(tmp_path)
        for i in range(10):
            _write_doc(
                tmp_path,
                f"2026-02-08-doc-{i}-adr",
                modified_line="modified: '2026-02-08'",
            )
        _uniform_mtime(tmp_path, datetime.date(2026, 6, 1))

        result = _check(tmp_path)

        infos = [
            d
            for d in result.diagnostics
            if d.severity == Severity.INFO and "Skipping staleness" in d.message
        ]
        assert len(infos) == 1
        assert infos[0].path is None
        assert "git-operation signature" in infos[0].message

    def test_stash_restore_two_date_clusters_suppresses_staleness(self, tmp_path: Path):
        # Regression for the archive-under-prek cascade (issue #235). prek
        # stashes unstaged changes before running the vault-fix hook; the
        # restore rewrites the reverted documents to today's mtime while the
        # rest keep the working tree's earlier checkout date. The vault's
        # mtimes then collapse onto TWO calendar dates rather than one. A
        # guard that only recognised a single dominant date let every
        # document read as stale and the fix rewrote the whole vault. The
        # two-instant guard must recognise the cluster and suppress.
        _skeleton(tmp_path)
        docs = [
            _write_doc(
                tmp_path,
                f"2026-01-{(i % 28) + 1:02d}-doc-{i}-adr",
                date_line=f"date: '2026-01-{(i % 28) + 1:02d}'",
                modified_line=f"modified: '2026-01-{(i % 28) + 1:02d}'",
            )
            for i in range(20)
        ]
        # Baseline checkout instant for the untouched majority.
        checkout = datetime.date(2026, 7, 20)
        for doc in docs:
            _set_mtime(doc, checkout)
        # Stash restore bumps a minority (5/20 = 25%) to a second date. The
        # dominant single date holds only 75 percent - under the old guard's
        # threshold - but the top two dates together cover 100 percent.
        restore = datetime.date(2026, 7, 23)
        for doc in docs[:5]:
            _set_mtime(doc, restore)

        result = _check(tmp_path, fix=True)

        stale_findings = [d for d in result.diagnostics if "Stale" in d.message]
        assert stale_findings == []
        assert result.fixed_count == 0
        infos = [d for d in result.diagnostics if "Skipping staleness" in d.message]
        assert len(infos) == 1
        assert "git-operation signature" in infos[0].message

    def test_below_threshold_does_not_trip_guard(self, tmp_path: Path):
        _skeleton(tmp_path)
        # Five distinct mtime dates across ten docs: the dominant date
        # holds 20 percent, well under the 80 percent clone threshold, so
        # staleness checks run and the info diagnostic is absent.
        docs = [
            _write_doc(
                tmp_path,
                f"2026-02-08-doc-{i}-adr",
                modified_line="modified: '2026-02-08'",
            )
            for i in range(10)
        ]
        for i, doc in enumerate(docs):
            _set_mtime(doc, datetime.date(2026, 3, 1 + i))

        result = _check(tmp_path)

        infos = [d for d in result.diagnostics if "Skipping staleness" in d.message]
        assert infos == []
        stale_findings = [d for d in result.diagnostics if "Stale" in d.message]
        assert len(stale_findings) == 10


class TestCheckResultShape:
    def test_check_name_and_supports_fix(self, tmp_path: Path):
        _skeleton(tmp_path)
        _write_doc(
            tmp_path,
            "2026-02-08-alpha-adr",
            modified_line="modified: '2026-02-08'",
        )
        _uniform_mtime(tmp_path, datetime.date(2026, 2, 8))

        result = _check(tmp_path)

        assert result.check_name == "modified-stamp"
        assert result.supports_fix is True

    def test_canonical_fresh_stamp_is_clean(self, tmp_path: Path):
        _skeleton(tmp_path)
        _write_doc(
            tmp_path,
            "2026-02-08-alpha-adr",
            modified_line="modified: '2026-02-08'",
        )
        _uniform_mtime(tmp_path, datetime.date(2026, 2, 8))

        result = _check(tmp_path)

        actionable = [
            d
            for d in result.diagnostics
            if d.severity in (Severity.WARNING, Severity.ERROR)
        ]
        assert actionable == []

    def test_feature_filter_scopes_findings(self, tmp_path: Path):
        _skeleton(tmp_path)
        _write_doc(tmp_path, "2026-02-08-alpha-adr", feature="alpha")
        _write_doc(tmp_path, "2026-02-08-beta-adr", feature="beta")
        _uniform_mtime(tmp_path, datetime.date(2026, 2, 8))

        graph = VaultGraph(tmp_path)
        result = check_modified_stamp(
            tmp_path, snapshot=graph.to_snapshot(), feature="alpha"
        )

        paths = {str(d.path) for d in result.diagnostics if d.path is not None}
        assert any("alpha" in p for p in paths)
        assert not any("beta" in p for p in paths)
