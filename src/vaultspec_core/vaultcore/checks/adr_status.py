"""Validate ADR status against the canonical taxonomy.

Checks that every Architecture Decision Record declares a status drawn from the
canonical :class:`~vaultspec_core.core.enums.AdrStatus` set, encoded in the body
H1 in the canonical backtick-quoted form, and that the body status agrees with
the supersession frontmatter. The canonical encoding is::

    # `feature` adr: `Title` | (**status:** `accepted`)

Surfaces, all as warnings so the suite never hard-fails an existing corpus:

- a status token outside the canonical set, or no parseable status at all;
- status declared in a legacy ``## Status`` section, even alongside the H1;
- a bare (unquoted) H1 token, which ``--fix`` normalizes to the quoted form;
- ``superseded_by`` set in frontmatter while the body status is not
  ``superseded`` (an unpropagated supersession), or the reverse mismatch.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ...core.adr import adr_status_marker, rewrite_adr_status
from ...core.enums import AdrStatus
from ...core.helpers import atomic_write
from ..markdown import iter_headings
from ..models import refresh_modified_stamp, vault_today
from ..parser import split_frontmatter
from ._base import CheckDiagnostic, CheckResult, Severity

if TYPE_CHECKING:
    from pathlib import Path

    from ._base import VaultSnapshot

__all__ = ["check_adr_status"]

logger = logging.getLogger(__name__)

_CANONICAL_TOKENS = ", ".join(s.value for s in AdrStatus)


def _is_adr(path: Path) -> bool:
    """Return ``True`` when *path* is an ADR document."""
    return path.parent.name == "adr" and path.suffix == ".md"


def _has_legacy_status_section(body: str) -> bool:
    """Return ``True`` when *body* declares status in a ``## Status`` section."""
    return any(
        heading.level == 2 and heading.text == "Status"
        for heading in iter_headings(body)
    )


def _normalize_h1_quote(doc_path: Path, root_dir: Path, token: str) -> bool:
    """Rewrite the H1 status token to the canonical backtick-quoted form.

    The read, the heading rewrite, the stamp refresh, and the write are one
    critical section on *doc_path*'s per-document advisory lock - the same
    sentinel ``execute_edit`` takes - so the replacement is always derived
    from the bytes it overwrites rather than from a revision a concurrent
    editor has since superseded.

    Args:
        doc_path: Absolute path to the ADR document.
        root_dir: Project root owning the document's ``.vault/``.
        token: The canonical status value observed in the snapshot.

    Returns:
        ``True`` when the file was modified.
    """
    from ..edit_engine import document_write_lock

    with document_write_lock(doc_path, root_dir):
        return _normalize_h1_quote_locked(doc_path, token)


def _normalize_h1_quote_locked(doc_path: Path, token: str) -> bool:
    """Perform the H1 quoting rewrite under *doc_path*'s already-held lock.

    Args:
        doc_path: Absolute path to the ADR document.
        token: The canonical status value observed in the snapshot.

    Returns:
        ``True`` when the file was modified.
    """
    try:
        raw = doc_path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return False

    newline = "\r\n" if "\r\n" in raw else "\n"
    normalized = raw.replace("\r\n", "\n")
    marker = adr_status_marker(split_frontmatter(normalized).body)
    # A quoting repair cannot restore snapshot authority over a later decision.
    if (
        marker is None
        or marker.quoted
        or AdrStatus.from_token(marker.token) != AdrStatus.from_token(token)
    ):
        return False
    rendered = rewrite_adr_status(normalized, token, quoted=True)
    if rendered is None:
        return False

    # The quoting rewrite is a content mutation, so refresh the recency stamp in
    # the same pass (mirroring adr_supersede); the helper preserves the line
    # ending convention, so apply it before reapplying CRLF below.
    rendered = refresh_modified_stamp(rendered, vault_today())
    new_content = rendered if newline == "\n" else rendered.replace("\n", newline)
    atomic_write(doc_path, new_content)
    logger.info("Normalized H1 status quoting in %s", doc_path.name)
    return True


def check_adr_status(
    root_dir: Path,
    *,
    snapshot: VaultSnapshot,
    feature: str | None = None,
    fix: bool = False,
) -> CheckResult:
    """Validate ADR status declarations against the canonical taxonomy.

    Args:
        root_dir: Project root directory.
        snapshot: Mapping of document paths to parsed ``(metadata, body)``.
        feature: Restrict checks to ADRs carrying this feature tag (without
            ``#``).
        fix: When ``True``, normalize a bare canonical H1 token to the quoted
            form. Other findings are advisory and never auto-fixed.

    Returns:
        :class:`~vaultspec_core.vaultcore.checks._base.CheckResult` with check
        name ``"adr-status"``.
    """
    result = CheckResult(check_name="adr-status", supports_fix=True)
    feat = feature.lstrip("#") if feature else None

    for path, (meta, body) in sorted(snapshot.items(), key=lambda kv: str(kv[0])):
        if not _is_adr(path):
            continue
        if feat is not None and feat not in {t.lstrip("#") for t in meta.tags}:
            continue

        rel_path = path.relative_to(root_dir)
        marker = adr_status_marker(body)
        legacy = _has_legacy_status_section(body)
        if legacy:
            result.diagnostics.append(
                CheckDiagnostic(
                    path=rel_path,
                    message=(
                        "ADR has a legacy '## Status' section; "
                        "status belongs in the canonical H1 token only"
                    ),
                    severity=Severity.WARNING,
                    fix_description=(
                        "Reconcile the status declarations against recorded "
                        "authority before removing the legacy declaration"
                    ),
                )
            )

        if marker is None:
            if not legacy:
                result.diagnostics.append(
                    CheckDiagnostic(
                        path=rel_path,
                        message="ADR has no parseable status in its H1",
                        severity=Severity.WARNING,
                        fix_description=(
                            "Establish the authorized status before adding "
                            "(**status:** `<value>`) to the H1; one of "
                            f"{_CANONICAL_TOKENS}"
                        ),
                    )
                )
            continue

        token, quoted = marker.token, marker.quoted
        status = AdrStatus.from_token(token)

        if status is None:
            result.diagnostics.append(
                CheckDiagnostic(
                    path=rel_path,
                    message=(
                        f"ADR status '{token}' is outside the canonical set "
                        f"({_CANONICAL_TOKENS})"
                    ),
                    severity=Severity.WARNING,
                    fix_description=(
                        "Establish the authorized status before setting "
                        "the H1 to a canonical value"
                    ),
                )
            )
            continue

        if not quoted:
            if fix and _normalize_h1_quote(path, root_dir, status.value):
                result.fixed_count += 1
                result.diagnostics.append(
                    CheckDiagnostic(
                        path=rel_path,
                        message=f"Fixed: quoted H1 status token `{status.value}`",
                        severity=Severity.INFO,
                    )
                )
            else:
                result.diagnostics.append(
                    CheckDiagnostic(
                        path=rel_path,
                        message=(
                            f"ADR status '{token}' is not backtick-quoted in the H1"
                        ),
                        severity=Severity.WARNING,
                        fixable=True,
                        fix_description="Wrap the H1 status token in backticks",
                    )
                )

        if meta.superseded_by and status is not AdrStatus.SUPERSEDED:
            result.diagnostics.append(
                CheckDiagnostic(
                    path=rel_path,
                    message=(
                        "ADR has 'superseded_by' in frontmatter but its body "
                        f"status is '{status.value}', not 'superseded'"
                    ),
                    severity=Severity.WARNING,
                    fix_description=(
                        "Inspect both records' supersession edges and authority; "
                        "repair the H1 only when the recorded transition is clear"
                    ),
                )
            )
        elif status is AdrStatus.SUPERSEDED and not meta.superseded_by:
            result.diagnostics.append(
                CheckDiagnostic(
                    path=rel_path,
                    message="ADR status is 'superseded' but has no 'superseded_by'",
                    severity=Severity.WARNING,
                    fix_description=(
                        "Find the authorized successor or correct the status "
                        "from recorded authority; do not infer a replacement"
                    ),
                )
            )

    return result
