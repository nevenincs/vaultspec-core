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
- **Stale** (the file's mtime date is strictly newer than the stamp's
  date) -> finding; the fix refreshes the stamp to the file's mtime date,
  surfacing hand edits the CLI mutators did not stamp.

Clone-signature guard. File mtime does not survive ``git clone``: a fresh
checkout rewrites every tracked file to one wall-clock instant, so every
document would falsely read as "modified today" and the staleness branch
would flag the entire vault. To avoid that noise, before emitting any
staleness finding this checker computes the modal mtime date across all
scanned documents; when 80 percent or more of the documents share a single
mtime date the run is treated as carrying the fresh-clone signature, every
staleness finding is suppressed for that run, and a single informational
diagnostic explains why. The missing, non-canonical, and unparseable
branches are unaffected by the guard - they read frontmatter, not mtime.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ...core.helpers import atomic_write
from ..models import normalize_date, parse_lenient_date
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

__all__ = ["check_modified_stamp"]

#: Threshold at or above which a shared mtime date is read as the
#: fresh-clone signature and staleness findings are suppressed.
_CLONE_SIGNATURE_RATIO = 0.8

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


def _filename_date(path: Path) -> str | None:
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

    Args:
        path: Document path to stat.

    Returns:
        The local-time date of the file's mtime, or ``None`` when the
        file cannot be stat'd.
    """
    import datetime

    try:
        ts = path.stat().st_mtime
    except OSError:
        return None
    return datetime.datetime.fromtimestamp(ts).date()


def _write_stamp(doc_path: Path, value: str) -> bool:
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
    non-canonical, unparseable, or stale relative to the file's mtime;
    under ``fix`` it adds, normalizes, or refreshes the stamp as the
    module docstring describes. The unparseable case is reported but
    never rewritten so a hand-entered value is never silently lost.

    Staleness findings are guarded against the fresh-clone signature:
    when at least :data:`_CLONE_SIGNATURE_RATIO` of the scanned documents
    share one mtime date the staleness branch is skipped for the whole
    run and a single informational diagnostic explains why.

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

    docs: list[tuple[Path, DocumentMetadata]] = []
    for doc_path, (metadata, _body) in snapshot.items():
        if feature:
            feat = feature.lstrip("#")
            if feat not in extract_feature_tags(metadata.tags):
                continue
        docs.append((doc_path, metadata))

    # Clone-signature detection: tally mtime dates across the documents in
    # scope and suppress staleness findings when one date dominates.
    mtime_dates: dict[datetime.date, int] = {}
    mtime_by_path: dict[Path, datetime.date | None] = {}
    for doc_path, _metadata in docs:
        md = _mtime_date(doc_path)
        mtime_by_path[doc_path] = md
        if md is not None:
            mtime_dates[md] = mtime_dates.get(md, 0) + 1

    total_with_mtime = sum(mtime_dates.values())
    clone_signature = False
    if total_with_mtime:
        dominant = max(mtime_dates.values())
        clone_signature = dominant / total_with_mtime >= _CLONE_SIGNATURE_RATIO

    if clone_signature:
        result.diagnostics.append(
            CheckDiagnostic(
                path=None,
                message=(
                    "Skipping staleness checks: "
                    f"{dominant} of {total_with_mtime} documents share one mtime "
                    "date (fresh-clone signature; file mtime does not survive "
                    "git clone, so staleness cannot be inferred this run)."
                ),
                severity=Severity.INFO,
            )
        )

    for doc_path, metadata in docs:
        rel_path = doc_path.relative_to(root_dir)
        raw_modified = metadata.modified

        if not raw_modified:
            backfill = normalize_date(metadata.date) or _filename_date(doc_path)
            if fix and backfill is not None and _write_stamp(doc_path, backfill):
                result.fixed_count += 1
                result.diagnostics.append(
                    CheckDiagnostic(
                        path=rel_path,
                        message=f"Added modified stamp '{backfill}'.",
                        severity=Severity.INFO,
                    )
                )
            else:
                fixable = backfill is not None
                fix_desc = f"add modified: '{backfill}'" if fixable else None
                result.diagnostics.append(
                    CheckDiagnostic(
                        path=rel_path,
                        message="Missing modified stamp.",
                        severity=Severity.WARNING,
                        fixable=fixable,
                        fix_description=fix_desc,
                    )
                )
            continue

        parsed = parse_lenient_date(raw_modified)
        if parsed is None:
            result.diagnostics.append(
                CheckDiagnostic(
                    path=rel_path,
                    message=(
                        f"Unparseable modified stamp '{raw_modified}'; "
                        "cannot auto-fix - repair the value by hand."
                    ),
                    severity=Severity.ERROR,
                    fixable=False,
                )
            )
            continue

        canonical = parsed.isoformat()
        # Non-canonical-but-parseable: the stored value is not the bare
        # canonical string (e.g. an ISO timestamp or yyyy/mm/dd).
        if raw_modified != canonical:
            if fix and _write_stamp(doc_path, canonical):
                result.fixed_count += 1
                result.diagnostics.append(
                    CheckDiagnostic(
                        path=rel_path,
                        message=(
                            f"Normalized modified stamp '{raw_modified}' "
                            f"-> '{canonical}'."
                        ),
                        severity=Severity.INFO,
                    )
                )
                continue
            result.diagnostics.append(
                CheckDiagnostic(
                    path=rel_path,
                    message=(
                        f"Non-canonical modified stamp '{raw_modified}'; "
                        f"canonical form is '{canonical}'."
                    ),
                    severity=Severity.WARNING,
                    fixable=True,
                    fix_description=f"rewrite to '{canonical}'",
                )
            )
            continue

        # Staleness: only when the run does not carry the clone signature.
        if clone_signature:
            continue
        mtime_date = mtime_by_path.get(doc_path)
        if mtime_date is not None and mtime_date > parsed:
            stale_value = mtime_date.isoformat()
            if fix and _write_stamp(doc_path, stale_value):
                result.fixed_count += 1
                result.diagnostics.append(
                    CheckDiagnostic(
                        path=rel_path,
                        message=(
                            f"Refreshed stale modified stamp '{canonical}' "
                            f"-> '{stale_value}' (file mtime is newer)."
                        ),
                        severity=Severity.INFO,
                    )
                )
            else:
                result.diagnostics.append(
                    CheckDiagnostic(
                        path=rel_path,
                        message=(
                            f"Stale modified stamp '{canonical}'; file mtime "
                            f"date '{stale_value}' is newer."
                        ),
                        severity=Severity.WARNING,
                        fixable=True,
                        fix_description=f"refresh to '{stale_value}'",
                    )
                )

    return result
