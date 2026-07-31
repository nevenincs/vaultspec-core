"""Tests for the ``modified-stamp`` vault health checker.

Exercises every semantic of
:func:`~vaultspec_core.vaultcore.checks.modified_stamp.check_modified_stamp`
against real on-disk documents (vault-orientation ADR decisions D3, D3b,
on the evidence source the modified-stamp-provenance ADR settled):

- a missing stamp is flagged and, under fix, backfilled from ``date:``
  or the filename ``yyyy-mm-dd`` prefix;
- a present-but-non-canonical yet parseable stamp is flagged and
  normalized to the canonical quoted form, preserving the parsed value;
- an unparseable stamp is flagged as an error and never rewritten;
- a stamp earlier than the document's own ``date:`` is raised to it;
- a stamp whose attested ``body_hash:`` no longer matches the live body is
  flagged stale and, under fix, refreshed to today and re-attested;
- a document attesting nothing is silent, and under fix is seeded without
  its stamp being touched;
- the check converges: running the fix and then re-checking reports clean,
  and file mtime - however it is rewritten - changes nothing.

All fixtures are real files. No mocks, patches, or skips.
"""

from __future__ import annotations

import datetime
import os
from typing import TYPE_CHECKING

import pytest

from ....config import reset_config
from ....graph import VaultGraph
from ...body_hash import document_body_digest
from ...models import vault_today
from .._base import CheckDiagnostic, CheckResult, Severity
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
    attested: bool = False,
    body: str | None = None,
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
        attested: When ``True``, a ``body_hash:`` line attesting the body
            written here is added, exactly as a stamping verb would leave
            it. When ``False`` the document attests nothing.
        body: Body prose after the frontmatter fence. Defaults to a
            one-heading body derived from *stem*.
        sub: ``.vault`` subdirectory.
        tag: Directory tag for the document.

    Returns:
        The written document path.
    """
    doc_body = f"# {stem}\n" if body is None else body
    lines = ["---", "tags:", f"  - '{tag}'", f"  - '#{feature}'"]
    if date_line is not None:
        lines.append(date_line)
    if modified_line is not None:
        lines.append(modified_line)
    if attested:
        lines.append(f"body_hash: '{document_body_digest(doc_body)}'")
    lines += ["---", "", doc_body]
    doc = root / ".vault" / sub / f"{stem}.md"
    doc.write_text("\n".join(lines), encoding="utf-8")
    return doc


def _rewrite_body(doc: Path, body: str) -> None:
    """Replace *doc*'s body prose, leaving its frontmatter untouched.

    Models exactly the permitted hand-edit: body prose changes, no verb
    stamps the document, and the frontmatter (including its now-outdated
    ``body_hash:``) is left as it stands.
    """
    text = doc.read_text(encoding="utf-8")
    head, _sep, _old = text.partition("\n---\n")
    doc.write_text(f"{head}\n---\n\n{body}", encoding="utf-8")


def _bulk_touch(root: Path, date: datetime.date) -> None:
    """Set every vault document's mtime to *date*.

    Models the content-neutral corpus-wide mtime rewrite - a clone, a
    checkout, a stash/restore cycle, a ``find -exec touch`` - that the
    retired mtime heuristic read as a corpus of hand edits.
    """
    ts = datetime.datetime(date.year, date.month, date.day, 12, 0, 0).timestamp()
    for doc in (root / ".vault").rglob("*.md"):
        os.utime(doc, (ts, ts))


def _check(root: Path, *, fix: bool = False) -> CheckResult:
    graph = VaultGraph(root)
    return check_modified_stamp(root, snapshot=graph.to_snapshot(), fix=fix)


def _actionable(result: CheckResult) -> list[CheckDiagnostic]:
    """Return the findings that would fail a gate (warnings and errors)."""
    return [
        d
        for d in result.diagnostics
        if d.severity in (Severity.WARNING, Severity.ERROR)
    ]


class TestMissingStamp:
    def test_missing_is_flagged(self, tmp_path: Path):
        _skeleton(tmp_path)
        _write_doc(tmp_path, "2026-02-08-alpha-adr")

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

        result = _check(tmp_path, fix=True)

        errors = [d for d in result.diagnostics if d.severity == Severity.ERROR]
        assert len(errors) == 1
        assert "Unparseable modified stamp 'tomorrow-ish'" in errors[0].message
        assert errors[0].fixable is False
        # The offending value is never dropped or rewritten. Seeding the
        # fingerprint alongside it is a fact about the body and leaves the
        # broken stamp - and the error - exactly as they stand.
        assert "modified: 'tomorrow-ish'" in doc.read_text(encoding="utf-8")

    def test_unparseable_survives_a_second_pass(self, tmp_path: Path):
        _skeleton(tmp_path)
        doc = _write_doc(
            tmp_path,
            "2026-02-08-alpha-adr",
            modified_line="modified: 'tomorrow-ish'",
        )

        _check(tmp_path, fix=True)
        second = _check(tmp_path, fix=True)

        errors = [d for d in second.diagnostics if d.severity == Severity.ERROR]
        assert len(errors) == 1
        assert second.fixed_count == 0
        assert "modified: 'tomorrow-ish'" in doc.read_text(encoding="utf-8")


class TestFingerprintStaleness:
    """Staleness is the disagreement between a document's attested
    ``body_hash:`` and the body it now carries - the only evidence of an
    unstamped hand edit that survives a clone, a checkout, or a touch."""

    def test_attested_unchanged_body_is_clean(self, tmp_path: Path):
        _skeleton(tmp_path)
        _write_doc(
            tmp_path,
            "2026-02-08-alpha-adr",
            modified_line="modified: '2026-02-08'",
            attested=True,
        )

        result = _check(tmp_path)

        assert _actionable(result) == []

    def test_hand_edited_body_is_flagged_stale(self, tmp_path: Path):
        _skeleton(tmp_path)
        doc = _write_doc(
            tmp_path,
            "2026-02-08-alpha-adr",
            modified_line="modified: '2026-02-08'",
            attested=True,
        )
        _rewrite_body(doc, "# 2026-02-08-alpha-adr\n\nA sentence nobody stamped.\n")

        result = _check(tmp_path)

        warnings = [d for d in result.diagnostics if d.severity == Severity.WARNING]
        assert len(warnings) == 1
        assert "Stale modified stamp '2026-02-08'" in warnings[0].message
        assert "no longer matches its attested fingerprint" in warnings[0].message
        assert warnings[0].fixable is True
        assert warnings[0].path == doc.relative_to(tmp_path)

    def test_fix_stamps_today_and_reattests(self, tmp_path: Path):
        _skeleton(tmp_path)
        doc = _write_doc(
            tmp_path,
            "2026-02-08-alpha-adr",
            modified_line="modified: '2026-02-08'",
            attested=True,
        )
        new_body = "# 2026-02-08-alpha-adr\n\nA sentence nobody stamped.\n"
        _rewrite_body(doc, new_body)

        result = _check(tmp_path, fix=True)

        assert result.fixed_count == 1
        text = doc.read_text(encoding="utf-8")
        assert f"modified: '{vault_today().isoformat()}'" in text
        assert f"body_hash: '{document_body_digest(new_body)}'" in text

    def test_whitespace_only_body_churn_is_not_an_edit(self, tmp_path: Path):
        """Trailing blank lines are formatting noise, not authorship.

        The canonical body strips outer whitespace precisely so an editor
        adding or dropping a final newline does not manufacture a finding.
        """
        _skeleton(tmp_path)
        doc = _write_doc(
            tmp_path,
            "2026-02-08-alpha-adr",
            modified_line="modified: '2026-02-08'",
            attested=True,
            body="# alpha\n\nProse.\n",
        )
        _rewrite_body(doc, "# alpha\n\nProse.\n\n\n")

        assert _actionable(_check(tmp_path)) == []

    def test_staleness_outranks_a_non_canonical_stamp(self, tmp_path: Path):
        """A form repair must not quietly absorb evidence of a body edit.

        The non-canonical fix rewrites the stamp to the value already on
        disk, and every fix re-attests the fingerprint - so repairing form
        first would file the edited body's fingerprint beside a pre-edit
        date and erase the edit permanently.
        """
        _skeleton(tmp_path)
        doc = _write_doc(
            tmp_path,
            "2026-02-08-alpha-adr",
            modified_line="modified: '2026/02/08'",
            attested=True,
        )
        _rewrite_body(doc, "# alpha\n\nUnstamped edit.\n")

        result = _check(tmp_path, fix=True)

        assert result.fixed_count == 1
        assert f"modified: '{vault_today().isoformat()}'" in doc.read_text(
            encoding="utf-8"
        )
        assert _actionable(_check(tmp_path)) == []

    def test_staleness_outranks_a_predating_stamp(self, tmp_path: Path):
        _skeleton(tmp_path)
        doc = _write_doc(
            tmp_path,
            "2026-02-08-alpha-adr",
            date_line="date: '2026-02-08'",
            modified_line="modified: '2026-01-01'",
            attested=True,
        )
        _rewrite_body(doc, "# alpha\n\nUnstamped edit.\n")

        result = _check(tmp_path, fix=True)

        assert result.fixed_count == 1
        assert f"modified: '{vault_today().isoformat()}'" in doc.read_text(
            encoding="utf-8"
        )
        assert _actionable(_check(tmp_path)) == []

    def test_crlf_rewrite_is_not_an_edit(self, tmp_path: Path):
        """A checkout that flips the corpus to CRLF changes no content.

        This is the exact failure class that disqualified mtime; a
        fingerprint sensitive to line endings would reintroduce it.
        """
        _skeleton(tmp_path)
        doc = _write_doc(
            tmp_path,
            "2026-02-08-alpha-adr",
            modified_line="modified: '2026-02-08'",
            attested=True,
        )
        lf = doc.read_bytes()
        doc.write_bytes(lf.replace(b"\n", b"\r\n"))

        assert _actionable(_check(tmp_path)) == []


class TestUnattestedIsSilent:
    """A document attesting nothing makes no claim about its body, so it
    earns no staleness finding - the body-schema attestation precedent."""

    def test_no_attestation_yields_no_finding(self, tmp_path: Path):
        _skeleton(tmp_path)
        _write_doc(
            tmp_path,
            "2026-02-08-alpha-adr",
            modified_line="modified: '2026-02-08'",
        )

        result = _check(tmp_path)

        assert _actionable(result) == []

    def test_fix_seeds_without_touching_the_stamp(self, tmp_path: Path):
        _skeleton(tmp_path)
        body = "# alpha\n\nAmnesty applies to the stamp, not the body.\n"
        doc = _write_doc(
            tmp_path,
            "2026-02-08-alpha-adr",
            modified_line="modified: '2026-02-08'",
            body=body,
        )

        result = _check(tmp_path, fix=True)

        text = doc.read_text(encoding="utf-8")
        assert result.fixed_count == 1
        # Amnesty: the historical stamp value stands exactly as it was.
        assert "modified: '2026-02-08'" in text
        assert f"body_hash: '{document_body_digest(body)}'" in text
        infos = [
            d
            for d in result.diagnostics
            if d.severity == Severity.INFO and "Seeded body fingerprint" in d.message
        ]
        assert len(infos) == 1

    def test_garbage_attestation_is_treated_as_absent(self, tmp_path: Path):
        # A hand-typed value was never computed from the body, so it is not
        # evidence: no staleness inference, and the fix replaces it with the
        # real fingerprint rather than reporting a false edit.
        _skeleton(tmp_path)
        doc = _write_doc(
            tmp_path,
            "2026-02-08-alpha-adr",
            modified_line="modified: '2026-02-08'",
        )
        text = doc.read_text(encoding="utf-8")
        doc.write_text(
            text.replace(
                "modified: '2026-02-08'",
                "modified: '2026-02-08'\nbody_hash: 'looks-about-right'",
            ),
            encoding="utf-8",
        )

        assert _actionable(_check(tmp_path)) == []

        _check(tmp_path, fix=True)
        assert "body_hash: 'sha256:" in doc.read_text(encoding="utf-8")


class TestConvergence:
    """The fix writes the comparison's own right-hand side, so a run always
    reaches a fixed point. This is the property the mtime implementation
    could not have: its fix invalidated the value it had just written."""

    def _seeded_vault(self, tmp_path: Path, count: int = 12) -> list[Path]:
        _skeleton(tmp_path)
        return [
            _write_doc(
                tmp_path,
                f"2026-02-{(i % 28) + 1:02d}-doc-{i}-adr",
                date_line=f"date: '2026-02-{(i % 28) + 1:02d}'",
                modified_line=f"modified: '2026-02-{(i % 28) + 1:02d}'",
                attested=True,
            )
            for i in range(count)
        ]

    def test_fix_then_check_is_clean(self, tmp_path: Path):
        docs = self._seeded_vault(tmp_path)
        for doc in docs:
            _rewrite_body(doc, f"# {doc.stem}\n\nUnstamped edit.\n")

        first = _check(tmp_path, fix=True)
        assert first.fixed_count == len(docs)

        after = _check(tmp_path)
        assert _actionable(after) == []

    def test_second_fix_run_is_a_no_op(self, tmp_path: Path):
        docs = self._seeded_vault(tmp_path)
        for doc in docs:
            _rewrite_body(doc, f"# {doc.stem}\n\nUnstamped edit.\n")

        _check(tmp_path, fix=True)
        bytes_after_first = {doc: doc.read_bytes() for doc in docs}

        second = _check(tmp_path, fix=True)

        assert second.fixed_count == 0
        assert _actionable(second) == []
        assert {doc: doc.read_bytes() for doc in docs} == bytes_after_first

    def test_repeated_checks_report_identically(self, tmp_path: Path):
        docs = self._seeded_vault(tmp_path)
        _rewrite_body(docs[0], "# edited\n\nOnly this one changed.\n")

        first = [(d.path, d.message, d.severity) for d in _check(tmp_path).diagnostics]
        second = [(d.path, d.message, d.severity) for d in _check(tmp_path).diagnostics]

        assert first == second
        assert len(_actionable(_check(tmp_path))) == 1

    def test_seeding_converges_on_an_unattested_corpus(self, tmp_path: Path):
        _skeleton(tmp_path)
        docs = [
            _write_doc(
                tmp_path,
                f"2026-02-{(i % 28) + 1:02d}-legacy-{i}-adr",
                date_line=f"date: '2026-02-{(i % 28) + 1:02d}'",
                modified_line=f"modified: '2026-02-{(i % 28) + 1:02d}'",
            )
            for i in range(12)
        ]
        stamps_before = {
            doc: doc.read_text(encoding="utf-8").split("modified: ")[1].split("\n")[0]
            for doc in docs
        }

        first = _check(tmp_path, fix=True)
        assert first.fixed_count == len(docs)

        second = _check(tmp_path, fix=True)
        assert second.fixed_count == 0
        assert _actionable(second) == []
        # Amnesty held across the whole corpus: not one stamp was rewritten.
        for doc, stamp in stamps_before.items():
            assert f"modified: {stamp}" in doc.read_text(encoding="utf-8")


class TestMtimeIsNotEvidence:
    """No filesystem timestamp is consulted anywhere in the checker.

    These pin the defect the modified-stamp-provenance decision removed: a
    content-neutral corpus-wide mtime rewrite used to fabricate a staleness
    finding for every document in the vault, and the fix then wrote a new
    generation of inferred dates."""

    def test_bulk_touch_fabricates_nothing(self, tmp_path: Path):
        _skeleton(tmp_path)
        docs = [
            _write_doc(
                tmp_path,
                f"2026-02-{(i % 28) + 1:02d}-doc-{i}-adr",
                date_line=f"date: '2026-02-{(i % 28) + 1:02d}'",
                modified_line=f"modified: '2026-02-{(i % 28) + 1:02d}'",
                attested=True,
            )
            for i in range(12)
        ]
        _bulk_touch(tmp_path, vault_today())

        result = _check(tmp_path, fix=True)

        assert _actionable(result) == []
        assert result.fixed_count == 0
        for i, doc in enumerate(docs):
            stamp = f"2026-02-{(i % 28) + 1:02d}"
            assert f"modified: '{stamp}'" in doc.read_text(encoding="utf-8")

    def test_future_mtime_fabricates_nothing(self, tmp_path: Path):
        _skeleton(tmp_path)
        doc = _write_doc(
            tmp_path,
            "2026-02-08-alpha-adr",
            modified_line="modified: '2026-02-08'",
            attested=True,
        )
        _bulk_touch(tmp_path, vault_today() + datetime.timedelta(days=30))

        result = _check(tmp_path, fix=True)

        assert _actionable(result) == []
        assert "modified: '2026-02-08'" in doc.read_text(encoding="utf-8")

    def test_no_suppression_diagnostic_survives(self, tmp_path: Path):
        # The git-signature guard is gone wholesale: with mtime out of the
        # evidence set there is nothing left for it to excuse, and a
        # heuristic that could suppress every staleness finding corpus-wide
        # is the mechanism that hid the last corruption.
        _skeleton(tmp_path)
        for i in range(10):
            _write_doc(
                tmp_path,
                f"2026-02-08-doc-{i}-adr",
                modified_line="modified: '2026-02-08'",
                attested=True,
            )
        _bulk_touch(tmp_path, vault_today())

        result = _check(tmp_path)

        assert not any("Skipping staleness" in d.message for d in result.diagnostics)
        assert not any("git-operation" in d.message for d in result.diagnostics)

    def test_stale_body_is_still_caught_after_a_bulk_touch(self, tmp_path: Path):
        # The inverse of the suppression guard: a real unstamped edit must
        # survive the very event that used to hide every finding.
        _skeleton(tmp_path)
        docs = [
            _write_doc(
                tmp_path,
                f"2026-02-08-doc-{i}-adr",
                modified_line="modified: '2026-02-08'",
                attested=True,
            )
            for i in range(10)
        ]
        _rewrite_body(docs[3], "# edited\n\nA real change.\n")
        _bulk_touch(tmp_path, vault_today())

        result = _check(tmp_path)

        warnings = [d for d in result.diagnostics if d.severity == Severity.WARNING]
        assert len(warnings) == 1
        assert warnings[0].path == docs[3].relative_to(tmp_path)


class TestModifiedPredatesDate:
    """A canonical ``modified:`` earlier than the document's own ``date:``
    is a nonsense state (D3b: the stamp starts equal to ``date:`` and only
    ever moves forward). The fingerprint compares the body against its own
    attestation, never against ``date:``, so without this check the value
    would sail through every other branch looking clean forever."""

    def test_modified_before_date_is_flagged(self, tmp_path: Path):
        _skeleton(tmp_path)
        doc = _write_doc(
            tmp_path,
            "2026-02-08-alpha-adr",
            date_line="date: '2026-02-08'",
            modified_line="modified: '2026-01-01'",
        )

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

        result = _check(tmp_path, fix=True)

        assert result.fixed_count == 1
        assert "modified: '2026-02-08'" in doc.read_text(encoding="utf-8")
        infos = [d for d in result.diagnostics if d.severity == Severity.INFO]
        assert any("raised to '2026-02-08'" in d.message for d in infos)

    def test_absurdly_old_modified_is_caught_by_the_floor(self, tmp_path: Path):
        # A year-1900 stamp is a valid, parseable date - not garbage per
        # parse_lenient_date - but nonsense relative to date:.
        _skeleton(tmp_path)
        doc = _write_doc(
            tmp_path,
            "2026-02-08-alpha-adr",
            date_line="date: '2026-02-08'",
            modified_line="modified: '1900-01-01'",
        )

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

        result = _check(tmp_path)

        assert not any("predates" in d.message for d in result.diagnostics)


class TestTimezoneCarryingStamp:
    """An ISO timestamp with an explicit zone offset must resolve to the
    same UTC calendar day the vault's other clocks (``vault_today``) use,
    not the offset's own literal wall-clock day."""

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

        result = _check(tmp_path)

        assert result.check_name == "modified-stamp"
        assert result.supports_fix is True

    def test_canonical_fresh_stamp_is_clean(self, tmp_path: Path):
        _skeleton(tmp_path)
        _write_doc(
            tmp_path,
            "2026-02-08-alpha-adr",
            modified_line="modified: '2026-02-08'",
            attested=True,
        )

        result = _check(tmp_path)

        assert _actionable(result) == []

    def test_feature_filter_scopes_findings(self, tmp_path: Path):
        _skeleton(tmp_path)
        _write_doc(tmp_path, "2026-02-08-alpha-adr", feature="alpha")
        _write_doc(tmp_path, "2026-02-08-beta-adr", feature="beta")

        graph = VaultGraph(tmp_path)
        result = check_modified_stamp(
            tmp_path, snapshot=graph.to_snapshot(), feature="alpha"
        )

        paths = {str(d.path) for d in result.diagnostics if d.path is not None}
        assert any("alpha" in p for p in paths)
        assert not any("beta" in p for p in paths)

    def test_feature_filter_scopes_seeding(self, tmp_path: Path):
        _skeleton(tmp_path)
        alpha = _write_doc(
            tmp_path,
            "2026-02-08-alpha-adr",
            feature="alpha",
            modified_line="modified: '2026-02-08'",
        )
        beta = _write_doc(
            tmp_path,
            "2026-02-08-beta-adr",
            feature="beta",
            modified_line="modified: '2026-02-08'",
        )

        graph = VaultGraph(tmp_path)
        check_modified_stamp(
            tmp_path, snapshot=graph.to_snapshot(), feature="alpha", fix=True
        )

        assert "body_hash:" in alpha.read_text(encoding="utf-8")
        assert "body_hash:" not in beta.read_text(encoding="utf-8")
