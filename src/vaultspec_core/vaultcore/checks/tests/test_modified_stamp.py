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
from ...models import vault_today
from .._base import Severity
from ..modified_stamp import check_modified_stamp

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

pytestmark = [pytest.mark.unit]


@pytest.fixture(autouse=True)
def reset_cfg() -> Generator[None]:
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

    def test_utc_stamped_instant_is_not_stale_across_local_day_boundary(
        self, tmp_path: Path
    ) -> None:
        """A document stamped and stat'd at the same instant is never
        stale, even when that instant's local calendar day differs from
        its UTC calendar day.

        Regression for the mtime/stamp clock-mismatch bug: ``_mtime_date``
        used to read the file's mtime through the naive local clock while
        every ``modified:``/``date:`` stamp is UTC-anchored. On a host
        east of UTC (this suite's environment is UTC+2), 23:30 on a UTC
        calendar day already reads as the following calendar day local, so
        a document scaffolded and stat'd in the very same instant read as
        if hand-edited a day in the future - false staleness with no edit
        involved, and under ``--fix`` a silent rewrite of ``modified:`` to
        a day past its own ``date:``.
        """
        _skeleton(tmp_path)
        self._diverse_fresh_fillers(tmp_path)

        doc = _write_doc(
            tmp_path,
            "2026-02-08-alpha-adr",
            date_line="date: '2026-02-08'",
            modified_line="modified: '2026-02-08'",
        )
        # 23:30 UTC on 2026-02-08: the same UTC calendar day as the stamp,
        # but already 2026-02-09 local at any positive UTC offset of 30
        # minutes or more.
        utc_instant = datetime.datetime(2026, 2, 8, 23, 30, 0, tzinfo=datetime.UTC)
        ts = utc_instant.timestamp()
        os.utime(doc, (ts, ts))

        result = _check(tmp_path)
        stale_findings = [d for d in result.diagnostics if "Stale" in d.message]
        assert stale_findings == []

        fixed = _check(tmp_path, fix=True)
        assert fixed.fixed_count == 0
        assert "modified: '2026-02-08'" in doc.read_text(encoding="utf-8")


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

    def test_small_vault_trivial_clustering_suppresses_genuine_staleness(
        self, tmp_path: Path
    ):
        """Documents accepted, deliberate behavior at low sample sizes.

        With only 3 documents, the vault can carry at most 2 distinct
        mtime dates or 3; whenever it carries 2 or fewer -
        :data:`_GIT_SIGNATURE_MAX_INSTANTS` - the top-2 tally is
        mathematically guaranteed to equal the total, so the ratio is
        always 100% regardless of whether a git operation actually
        happened. This is not fixable by adding a minimum-sample floor:
        that would only flip the failure mode, reintroducing false "stale"
        floods (and, under ``--fix``, destructive rewrites) for exactly the
        small freshly-cloned vaults the guard exists to protect. Between a
        non-destructive missed warning and a destructive silent rewrite,
        the guard is deliberately biased toward the former - so a small
        vault with a coincidental 2-of-3 mtime cluster suppresses a
        genuinely stale third document too. This test pins that trade-off
        so it reads as intentional, not an oversight.
        """
        _skeleton(tmp_path)
        stale = _write_doc(
            tmp_path,
            "2026-01-01-stale-adr",
            date_line="date: '2026-01-01'",
            modified_line="modified: '2026-01-01'",
        )
        _set_mtime(stale, datetime.date(2026, 5, 1))
        fresh_a = _write_doc(
            tmp_path,
            "2026-02-08-fresh-a-adr",
            date_line="date: '2026-02-08'",
            modified_line="modified: '2026-02-08'",
        )
        fresh_b = _write_doc(
            tmp_path,
            "2026-02-08-fresh-b-adr",
            date_line="date: '2026-02-08'",
            modified_line="modified: '2026-02-08'",
        )
        _set_mtime(fresh_a, datetime.date(2026, 2, 8))
        _set_mtime(fresh_b, datetime.date(2026, 2, 8))

        result = _check(tmp_path)

        infos = [d for d in result.diagnostics if "Skipping staleness" in d.message]
        assert len(infos) == 1
        stale_findings = [d for d in result.diagnostics if "Stale" in d.message]
        assert stale_findings == []


class TestModifiedPredatesDate:
    """A canonical ``modified:`` earlier than the document's own ``date:``
    is a nonsense state (D3b: the stamp starts equal to ``date:`` and only
    ever moves forward). Staleness only ever compares against mtime, so
    without this check the value would sail through every other branch
    looking clean forever."""

    def test_modified_before_date_is_flagged(self, tmp_path: Path):
        _skeleton(tmp_path)
        doc = _write_doc(
            tmp_path,
            "2026-02-08-alpha-adr",
            date_line="date: '2026-02-08'",
            modified_line="modified: '2026-01-01'",
        )
        _uniform_mtime(tmp_path, datetime.date(2026, 2, 8))

        result = _check(tmp_path)

        warnings = [d for d in result.diagnostics if d.severity == Severity.WARNING]
        assert len(warnings) == 1
        assert "predates its own date" in warnings[0].message
        assert warnings[0].fixable is True
        # Never auto-fixed without --fix: the original value survives.
        assert "modified: '2026-01-01'" in doc.read_text(encoding="utf-8")

    def test_fix_raises_modified_to_date(self, tmp_path: Path):
        _skeleton(tmp_path)
        doc = _write_doc(
            tmp_path,
            "2026-02-08-alpha-adr",
            date_line="date: '2026-02-08'",
            modified_line="modified: '2026-01-01'",
        )
        _uniform_mtime(tmp_path, datetime.date(2026, 2, 8))

        result = _check(tmp_path, fix=True)

        assert result.fixed_count == 1
        assert "modified: '2026-02-08'" in doc.read_text(encoding="utf-8")
        infos = [d for d in result.diagnostics if d.severity == Severity.INFO]
        assert any("raised to '2026-02-08'" in d.message for d in infos)

    def test_absurdly_old_modified_is_caught_by_the_floor(self, tmp_path: Path):
        # A year-1900 stamp is a valid, parseable date - not garbage per
        # parse_lenient_date - but nonsense relative to date:. The floor
        # check catches it long before mtime would (mtime staleness would
        # also fire, but only on a run the git-signature guard permits).
        _skeleton(tmp_path)
        doc = _write_doc(
            tmp_path,
            "2026-02-08-alpha-adr",
            date_line="date: '2026-02-08'",
            modified_line="modified: '1900-01-01'",
        )
        _uniform_mtime(tmp_path, datetime.date(2026, 2, 8))

        result = _check(tmp_path, fix=True)

        assert result.fixed_count == 1
        assert "modified: '2026-02-08'" in doc.read_text(encoding="utf-8")

    def test_modified_equal_to_date_is_not_flagged(self, tmp_path: Path):
        _skeleton(tmp_path)
        _write_doc(
            tmp_path,
            "2026-02-08-alpha-adr",
            date_line="date: '2026-02-08'",
            modified_line="modified: '2026-02-08'",
        )
        _uniform_mtime(tmp_path, datetime.date(2026, 2, 8))

        result = _check(tmp_path)

        assert not any("predates" in d.message for d in result.diagnostics)


class TestFutureMtime:
    """A file mtime ahead of today (clock skew, a bad archive, a manual
    ``os.utime``) must never be written verbatim into ``modified:`` - that
    would durably corrupt the corpus, since the stamp could never again
    register as stale until real wall-clock time caught up to it."""

    def _diverse_fresh_fillers(self, tmp_path: Path, count: int = 9) -> None:
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

    def test_future_mtime_is_flagged_stale(self, tmp_path: Path):
        _skeleton(tmp_path)
        doc = _write_doc(
            tmp_path,
            "2026-02-08-alpha-adr",
            date_line="date: '2026-02-08'",
            modified_line="modified: '2026-02-08'",
        )
        future = vault_today() + datetime.timedelta(days=30)
        _set_mtime(doc, future)
        self._diverse_fresh_fillers(tmp_path)

        result = _check(tmp_path)

        stale_findings = [d for d in result.diagnostics if "Stale" in d.message]
        assert len(stale_findings) == 1
        assert "beyond today" in stale_findings[0].message

    def test_fix_clamps_future_mtime_to_today_not_the_raw_future_date(
        self, tmp_path: Path
    ):
        _skeleton(tmp_path)
        doc = _write_doc(
            tmp_path,
            "2026-02-08-alpha-adr",
            date_line="date: '2026-02-08'",
            modified_line="modified: '2026-02-08'",
        )
        future = vault_today() + datetime.timedelta(days=30)
        _set_mtime(doc, future)
        self._diverse_fresh_fillers(tmp_path)

        result = _check(tmp_path, fix=True)

        assert result.fixed_count == 1
        today_stamp = vault_today().isoformat()
        assert f"modified: '{today_stamp}'" in doc.read_text(encoding="utf-8")
        # The raw future mtime date was never written.
        assert future.isoformat() not in doc.read_text(encoding="utf-8")


class TestTimezoneCarryingStamp:
    """An ISO timestamp with an explicit zone offset must resolve to the
    same UTC calendar day the vault's other clocks (mtime, ``vault_today``)
    use, not the offset's own literal wall-clock day."""

    def test_offset_crossing_utc_midnight_normalizes_to_the_utc_day(
        self, tmp_path: Path
    ):
        # 23:00 on 2026-02-08 at UTC-05:00 is 2026-02-09T04:00:00 in UTC:
        # the canonical value must land on the 9th, not the offset's own
        # local calendar day (the 8th).
        _skeleton(tmp_path)
        doc = _write_doc(
            tmp_path,
            "2026-02-08-alpha-adr",
            date_line="date: '2026-02-08'",
            modified_line="modified: '2026-02-08T23:00:00-05:00'",
        )
        _uniform_mtime(tmp_path, datetime.date(2026, 2, 9))

        result = _check(tmp_path, fix=True)

        assert result.fixed_count == 1
        assert "modified: '2026-02-09'" in doc.read_text(encoding="utf-8")


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
