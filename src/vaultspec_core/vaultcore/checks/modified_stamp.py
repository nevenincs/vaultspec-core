"""Check and optionally fix the CLI-maintained ``modified:`` frontmatter stamp.

Reconciles the ``modified:`` recency stamp introduced by the
vault-orientation ADR (decisions D3 and D3b). The stamp is set equal to
``date:`` at scaffold time and refreshed by every mutating CLI verb, but
the permitted body-prose hand-edit path means a hand-touched document can
drift: the field may be missing, mis-formatted, or staler than the file
on disk. This checker is the reconciliation half of that contract.

Finding semantics (D3b):

- **Missing** ``modified:`` -> finding; the fix adds it, valued from the
  leniently-parsed ``date:`` field, or from the filename's ``yyyy-mm-dd``
  prefix when ``date:`` is absent or itself unparseable.
- **Present but non-canonical yet lenient-parseable** (unquoted scalar,
  ISO timestamp, ``yyyy/mm/dd``, and the other forms
  :func:`~vaultspec_core.vaultcore.models.parse_lenient_date` accepts)
  -> finding; the fix rewrites the field to the canonical quoted
  ``yyyy-mm-dd`` form, preserving the parsed value (never today's date).
- **Unparseable** ``modified:`` -> finding, never auto-fixed and never
  dropped; the message names the offending value so a human can repair it.
- **Predates** ``date:`` (a canonical, parseable ``modified:`` that is
  strictly earlier than the document's own ``date:``) -> finding; the
  stamp can never legitimately precede the day the document was scaffolded,
  so the fix raises it to ``date:``. Checked independent of file mtime and
  of the git-operation guard below, since it is a pure frontmatter
  comparison a clone or checkout cannot manufacture or hide.
- **Stale** (the file's mtime date is strictly newer than the stamp's
  date) -> finding; the fix refreshes the stamp to the file's mtime date,
  surfacing hand edits the CLI mutators did not stamp. A future mtime
  (clock skew, a bad archive, a manual ``os.utime``) is clamped to today
  before it is ever written, so the stamp can never be pushed ahead of the
  vault's own clock.

Git-operation guard. File mtime does not survive git operations: a fresh
checkout rewrites every tracked file to one wall-clock instant, and a
pre-commit stash/restore cycle rewrites the reverted files to a second
instant, so the affected documents would falsely read as "modified today"
and the staleness branch would flag the whole vault. That last case is the
sharp one: prek stashes unstaged changes before running hooks, and when the
restore lands on a different calendar day from the working tree's checkout,
the vault's mtimes collapse onto two dates rather than one - defeating a
guard that only recognises a single dominant date. To avoid that noise,
before emitting any staleness finding this checker tallies the mtime date of
every scanned document; when the largest few mtime dates (a fresh clone is
one such wall-clock instant, a stash/restore cycle is two;
:data:`_GIT_SIGNATURE_MAX_INSTANTS`) together account for at least
:data:`_GIT_SIGNATURE_RATIO` of the documents, the run is treated as
carrying a git-operation signature, every staleness finding is suppressed
for that run, and a single informational diagnostic explains why. The
missing, non-canonical, unparseable, and predates-date branches are
unaffected by the guard - they read frontmatter, not mtime.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ...core.helpers import atomic_write
from ..models import normalize_date, parse_lenient_date, vault_today
from ._base import (
    CheckDiagnostic,
    CheckResult,
    Severity,
    VaultSnapshot,
    extract_feature_tags,
)

if TYPE_CHECKING:
    import datetime
    from pathlib import Path

    from ..models import DocumentMetadata

__all__ = ["check_modified_stamp", "filename_date", "write_stamp"]

#: Fraction of documents which, once concentrated on the largest few mtime
#: dates, is read as a git-operation signature and suppresses staleness.
_GIT_SIGNATURE_RATIO = 0.8

#: Number of largest mtime-date buckets whose combined share is measured
#: against :data:`_GIT_SIGNATURE_RATIO`. A fresh clone collapses every file
#: onto one wall-clock instant; a pre-commit stash/restore cycle spanning a
#: calendar day adds a second. Two buckets model both without treating a
#: vault of genuinely diverse hand-edit dates (many small buckets) as an
#: artifact, so localized staleness still surfaces.
_GIT_SIGNATURE_MAX_INSTANTS = 2

#: Leading ``yyyy-mm-dd`` prefix on a vault filename, the scaffold-time
#: date anchor used when ``date:`` is absent or unparseable.
_FILENAME_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")

#: Frontmatter ``modified:`` line, capturing leading whitespace so an
#: indented key is rewritten in place rather than duplicated.
_MODIFIED_LINE_RE = re.compile(r"^(?P<indent>[ \t]*)modified:[^\n]*$", re.MULTILINE)

#: Frontmatter ``date:`` line, the insertion anchor when ``modified:`` is
#: absent (the new stamp lands directly after it, matching its layout).
#: The trailing newline is optional so a ``date:`` line that is the last
#: line of the frontmatter block (no ``\n`` before the closing fence,
#: which the fence match strips) still anchors the insertion.
_DATE_LINE_RE = re.compile(
    r"^(?P<indent>[ \t]*)date:[^\n]*(?P<eol>\r\n|\n|$)", re.MULTILINE
)


def filename_date(path: Path) -> str | None:
    """Return the canonical ``yyyy-mm-dd`` filename prefix, or ``None``.

    Args:
        path: Document path whose stem may carry a date prefix.

    Returns:
        The leniently-parsed canonical date string when the filename
        begins with a parseable ``yyyy-mm-dd`` prefix, else ``None``.
    """
    match = _FILENAME_DATE_RE.match(path.name)
    if match is None:
        return None
    return normalize_date(match.group(1))


def _mtime_date(path: Path) -> datetime.date | None:
    """Return the file's modification time as a calendar date.

    Read in UTC so this side of the staleness comparison uses the same
    clock as the ``modified:``/``date:`` stamps every CLI mutator writes
    (:func:`~vaultspec_core.vaultcore.models.refresh_modified_stamp`
    callers and scaffold-time stamping both anchor on UTC). A local-time
    read would disagree with a UTC-stamped document for roughly half the
    day, in either direction of the offset: east of UTC the local
    calendar day is already ahead, so a document stamped and stat'd in
    the same instant reads as if edited a day in the future - the exact
    false-staleness bug this function exists to not reintroduce.

    Args:
        path: Document path to stat.

    Returns:
        The UTC-calendar date of the file's mtime, or ``None`` when the
        file cannot be stat'd.
    """
    import datetime

    try:
        ts = path.stat().st_mtime
    except OSError:
        return None
    return datetime.datetime.fromtimestamp(ts, tz=datetime.UTC).date()


def write_stamp(doc_path: Path, value: str) -> bool:
    """Add or rewrite the ``modified:`` stamp to *value* in place.

    Operates on full document text and preserves every other byte,
    including the source CRLF/LF convention. When the field already
    exists its value is rewritten (keeping indentation); when absent it
    is inserted directly after the ``date:`` line. A document with no
    frontmatter fence, or one missing both ``modified:`` and ``date:``,
    is left untouched (no canonical anchor exists).

    Args:
        doc_path: Document to rewrite.
        value: Canonical ``yyyy-mm-dd`` date string to stamp.

    Returns:
        ``True`` when the file was rewritten, ``False`` otherwise.
    """
    # Guard against a stale-cased path from a snapshot built before a
    # sibling checker's case-only rename. On a case-insensitive
    # filesystem ``Path.exists`` and ``open`` both succeed for the wrong
    # casing, and ``atomic_write`` would resurrect the old-cased name. A
    # case-sensitive parent-directory listing check confirms the exact
    # name is the one on disk before we touch it; if it is not, the stamp
    # is skipped and the next clean pass stamps the correctly-cased file.
    try:
        if doc_path.name not in {entry.name for entry in doc_path.parent.iterdir()}:
            return False
    except OSError:
        return False

    try:
        raw = doc_path.read_bytes()
        content = raw.decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return False

    source_newline = "\r\n" if "\r\n" in content else "\n"
    text = content.replace("\r\n", "\n")

    fence = re.match(r"^(﻿?)---[ \t]*\n(.*?)\n---", text, re.DOTALL)
    if not fence:
        return False

    block_start = fence.start(2)
    block_end = fence.end(2)
    frontmatter = text[block_start:block_end]
    canonical = f"'{value}'"

    existing = _MODIFIED_LINE_RE.search(frontmatter)
    if existing is not None:
        indent = existing.group("indent")
        replacement = f"{indent}modified: {canonical}"
        new_frontmatter = (
            frontmatter[: existing.start()]
            + replacement
            + frontmatter[existing.end() :]
        )
        new_text = text[:block_start] + new_frontmatter + text[block_end:]
    else:
        date_line = _DATE_LINE_RE.search(frontmatter)
        if date_line is None:
            return False
        indent = date_line.group("indent")
        insert_at = block_start + date_line.end()
        if date_line.group("eol"):
            # Date line carries its own newline: drop the new stamp on the
            # following line, terminated so the next line is undisturbed.
            stamp_line = f"{indent}modified: {canonical}\n"
        else:
            # Date line is the last line of the block (its newline was
            # consumed by the closing-fence match): open a new line first.
            stamp_line = f"\n{indent}modified: {canonical}"
        new_text = text[:insert_at] + stamp_line + text[insert_at:]

    rendered = (
        new_text if source_newline == "\n" else new_text.replace("\n", source_newline)
    )
    bak = doc_path.with_suffix(doc_path.suffix + ".bak")
    bak.write_bytes(raw)
    try:
        atomic_write(doc_path, rendered)
    except Exception:
        if bak.exists():
            bak.replace(doc_path)
        raise
    bak.unlink(missing_ok=True)
    return True


@dataclass(frozen=True)
class _Finding:
    """One reconciliation finding, before it is reported or applied.

    Every branch of the checker resolves to this single shape, so the
    report-vs-fix decision lives in one place (:func:`_emit`) rather than
    being re-spelled per branch.

    Attributes:
        message: Reported when the stamp is left as it stands.
        severity: Severity carried by that report.
        stamp: Canonical value ``--fix`` writes, or ``None`` when the
            finding can never be auto-fixed - an unparseable value, or a
            missing stamp with no ``date:``/filename anchor to backfill
            from. ``None`` is also what makes the report unfixable.
        fixed_message: Reported instead when ``--fix`` writes the stamp.
        fix_description: Corrective action named on the unfixed report.

    Note:
        ``fixed_message`` and ``fix_description`` are read only when
        ``stamp`` is not ``None``, so a builder may leave them at their
        defaults - or interpolate an absent stamp into them - whenever it
        yields ``stamp=None``.
    """

    message: str
    severity: Severity
    stamp: str | None
    fixed_message: str = ""
    fix_description: str | None = None


def _missing_finding(doc_path: Path, metadata: DocumentMetadata) -> _Finding:
    """Build the finding for an absent ``modified:`` field."""
    backfill = normalize_date(metadata.date) or filename_date(doc_path)
    return _Finding(
        message="Missing modified stamp.",
        severity=Severity.WARNING,
        stamp=backfill,
        fixed_message=f"Added modified stamp '{backfill}'.",
        fix_description=f"add modified: '{backfill}'",
    )


def _unparseable_finding(raw_modified: str) -> _Finding:
    """Build the finding for a ``modified:`` value no parser accepts."""
    return _Finding(
        message=(
            f"Unparseable modified stamp '{raw_modified}'; "
            "cannot auto-fix - repair the value by hand."
        ),
        severity=Severity.ERROR,
        stamp=None,
    )


def _noncanonical_finding(raw_modified: str, canonical: str) -> _Finding:
    """Build the finding for a parseable but non-canonical ``modified:``."""
    return _Finding(
        message=(
            f"Non-canonical modified stamp '{raw_modified}'; "
            f"canonical form is '{canonical}'."
        ),
        severity=Severity.WARNING,
        stamp=canonical,
        fixed_message=(f"Normalized modified stamp '{raw_modified}' -> '{canonical}'."),
        fix_description=f"rewrite to '{canonical}'",
    )


def _predates_finding(canonical: str, date_parsed: datetime.date) -> _Finding:
    """Build the finding for a stamp older than the document's ``date:``."""
    floor_value = date_parsed.isoformat()
    return _Finding(
        message=(
            f"Modified stamp '{canonical}' predates its own "
            f"date '{floor_value}'; a stamp cannot be older "
            "than the document it stamps."
        ),
        severity=Severity.WARNING,
        stamp=floor_value,
        fixed_message=(
            f"Modified stamp '{canonical}' predated date "
            f"'{floor_value}'; raised to '{floor_value}'."
        ),
        fix_description=f"raise to '{floor_value}'",
    )


def _stale_finding(
    canonical: str, mtime_date: datetime.date, today: datetime.date
) -> _Finding:
    """Build the finding for a stamp the file's mtime has outrun.

    A future mtime (clock skew, a bad archive, a manual ``os.utime``) is
    clamped to *today*: writing the raw future date into ``modified:``
    would durably corrupt the corpus - the stamp could never register as
    stale again until real wall-clock time caught up to it, silently
    masking every later edit.
    """
    future_mtime = mtime_date > today
    effective_mtime = today if future_mtime else mtime_date
    stale_value = effective_mtime.isoformat()
    reason = (
        f"file mtime '{mtime_date.isoformat()}' is beyond today; "
        f"clamped to today's date"
        if future_mtime
        else "file mtime is newer"
    )
    return _Finding(
        message=(
            f"Stale modified stamp '{canonical}'; '{stale_value}' is newer ({reason})."
        ),
        severity=Severity.WARNING,
        stamp=stale_value,
        fixed_message=(
            f"Refreshed stale modified stamp '{canonical}' "
            f"-> '{stale_value}' ({reason})."
        ),
        fix_description=f"refresh to '{stale_value}'",
    )


def _classify(
    doc_path: Path,
    metadata: DocumentMetadata,
    *,
    mtime_date: datetime.date | None,
    today: datetime.date,
    check_staleness: bool,
) -> _Finding | None:
    """Return the single finding *doc_path* earns, or ``None`` when clean.

    The branches are ordered by how much they know: each one is only
    reached once the cheaper diagnoses above it have been ruled out, so
    exactly one finding is ever produced per document.

    Args:
        doc_path: Document being reconciled.
        metadata: Its parsed frontmatter.
        mtime_date: Its UTC mtime date, or ``None`` when unreadable.
        today: The vault's current date, the clamp ceiling for staleness.
        check_staleness: ``False`` when the run carries the git-operation
            signature, which suppresses the mtime branch only.

    Returns:
        The finding, or ``None`` when the stamp is canonical, no earlier
        than ``date:``, and not outrun by the file's mtime.
    """
    raw_modified = metadata.modified
    if not raw_modified:
        return _missing_finding(doc_path, metadata)

    parsed = parse_lenient_date(raw_modified)
    if parsed is None:
        return _unparseable_finding(raw_modified)

    # Non-canonical-but-parseable: the stored value is not the bare
    # canonical string (e.g. an ISO timestamp or yyyy/mm/dd).
    canonical = parsed.isoformat()
    if raw_modified != canonical:
        return _noncanonical_finding(raw_modified, canonical)

    # Semantic floor: modified: must never predate date: (D3b's own
    # invariant - the stamp starts equal to date: at scaffold and only
    # ever moves forward). A value already earlier than date:, whether
    # hand-entered or inherited from a pre-canonicalization edit, would
    # otherwise sail through the canonical-format and staleness checks
    # looking clean forever: staleness only ever compares against
    # mtime, never against date:, so this is the only place that
    # invariant is enforced. Independent of the git-operation guard -
    # it reads frontmatter, not mtime, so a clone or checkout cannot
    # manufacture or hide it.
    date_parsed = parse_lenient_date(metadata.date)
    if date_parsed is not None and parsed < date_parsed:
        return _predates_finding(canonical, date_parsed)

    if not check_staleness or mtime_date is None or mtime_date <= parsed:
        return None
    return _stale_finding(canonical, mtime_date, today)


def _emit(
    result: CheckResult,
    finding: _Finding,
    *,
    doc_path: Path,
    rel_path: Path,
    fix: bool,
) -> None:
    """Record *finding* on *result*, applying it first when asked to.

    Under ``fix`` an auto-fixable finding is written to disk and reported
    as an informational repair; a finding that is not auto-fixable, or one
    whose write is refused (no ``date:`` anchor, a stale-cased path), falls
    through to the unfixed report so it is never silently dropped.
    """
    if fix and finding.stamp is not None and write_stamp(doc_path, finding.stamp):
        result.fixed_count += 1
        result.diagnostics.append(
            CheckDiagnostic(
                path=rel_path,
                message=finding.fixed_message,
                severity=Severity.INFO,
            )
        )
        return

    fixable = finding.stamp is not None
    result.diagnostics.append(
        CheckDiagnostic(
            path=rel_path,
            message=finding.message,
            severity=finding.severity,
            fixable=fixable,
            fix_description=finding.fix_description if fixable else None,
        )
    )


def _scoped_docs(
    snapshot: VaultSnapshot, feature: str | None
) -> list[tuple[Path, DocumentMetadata]]:
    """Return the ``(path, metadata)`` pairs in scope for this run."""
    if not feature:
        return [
            (doc_path, metadata) for doc_path, (metadata, _body) in snapshot.items()
        ]
    feat = feature.lstrip("#")
    return [
        (doc_path, metadata)
        for doc_path, (metadata, _body) in snapshot.items()
        if feat in extract_feature_tags(metadata.tags)
    ]


def _git_signature_diagnostic(
    mtime_dates: Counter[datetime.date],
) -> CheckDiagnostic | None:
    """Return the suppression diagnostic when the run looks like a git operation.

    The largest few mtime dates (:data:`_GIT_SIGNATURE_MAX_INSTANTS`) are
    the wall-clock instants git operations rewrite files to; when they
    together cover at least :data:`_GIT_SIGNATURE_RATIO` of the documents
    carrying an mtime, staleness cannot be inferred this run.

    Args:
        mtime_dates: Tally of mtime dates across the documents in scope.

    Returns:
        The single informational diagnostic explaining the suppression, or
        ``None`` when the run carries no git-operation signature. A
        non-``None`` return is itself the signal that staleness is
        suppressed - the guard is active exactly when it is explained.
    """
    total_with_mtime = sum(mtime_dates.values())
    if not total_with_mtime:
        return None

    concentrated = sum(
        count for _date, count in mtime_dates.most_common(_GIT_SIGNATURE_MAX_INSTANTS)
    )
    if concentrated / total_with_mtime < _GIT_SIGNATURE_RATIO:
        return None

    instants = min(_GIT_SIGNATURE_MAX_INSTANTS, len(mtime_dates))
    return CheckDiagnostic(
        path=None,
        message=(
            "Skipping staleness checks: "
            f"{concentrated} of {total_with_mtime} documents cluster on "
            f"{instants} mtime date(s) (git-operation signature; file mtime "
            "does not survive clone, checkout, or a stash/restore cycle, so "
            "staleness cannot be inferred this run)."
        ),
        severity=Severity.INFO,
    )


def check_modified_stamp(
    root_dir: Path,
    *,
    snapshot: VaultSnapshot,
    feature: str | None = None,
    fix: bool = False,
) -> CheckResult:
    """Validate and reconcile the ``modified:`` recency stamp on every document.

    Implements the reconciliation half of the vault-orientation ADR
    (decisions D3, D3b). For each scanned document the checker reports a
    finding when the ``modified:`` stamp is missing, present but
    non-canonical, unparseable, earlier than the document's own ``date:``,
    or stale relative to the file's mtime; under ``fix`` it adds,
    normalizes, raises, or refreshes the stamp as the module docstring
    describes. The unparseable case is reported but never rewritten so a
    hand-entered value is never silently lost, and a future mtime is
    clamped to today rather than ever written verbatim.

    Staleness findings are guarded against git-operation mtime rewrites:
    when the largest few mtime dates (:data:`_GIT_SIGNATURE_MAX_INSTANTS`)
    together cover at least :data:`_GIT_SIGNATURE_RATIO` of the scanned
    documents the staleness branch is skipped for the whole run and a
    single informational diagnostic explains why. This covers both a fresh
    clone (one instant) and a pre-commit stash/restore cycle (two).

    Args:
        root_dir: Project root directory.
        snapshot: Pre-built snapshot mapping document paths to parsed
            ``(metadata, body)`` tuples.
        feature: Restrict checks to documents carrying this feature tag
            (without ``#``).
        fix: When ``True``, add missing stamps, normalize non-canonical
            ones, and refresh stale ones; unparseable values are reported
            but left untouched.

    Returns:
        :class:`~vaultspec_core.vaultcore.checks._base.CheckResult` with
        check name ``"modified-stamp"``.
    """
    result = CheckResult(check_name="modified-stamp", supports_fix=True)
    today = vault_today()
    docs = _scoped_docs(snapshot, feature)

    # Git-operation detection: tally mtime dates across the documents in
    # scope and suppress staleness findings when the largest few dates -
    # the wall-clock instants git operations rewrite files to - dominate.
    mtime_by_path = {doc_path: _mtime_date(doc_path) for doc_path, _metadata in docs}
    guard = _git_signature_diagnostic(
        Counter(md for md in mtime_by_path.values() if md is not None)
    )
    if guard is not None:
        result.diagnostics.append(guard)

    for doc_path, metadata in docs:
        finding = _classify(
            doc_path,
            metadata,
            mtime_date=mtime_by_path[doc_path],
            today=today,
            check_staleness=guard is None,
        )
        if finding is not None:
            _emit(
                result,
                finding,
                doc_path=doc_path,
                rel_path=doc_path.relative_to(root_dir),
                fix=fix,
            )

    return result
