"""Check and optionally fix vault document frontmatter.

Validates every document against DocumentMetadata.validate() rules:
- At least 2 tags (one directory tag, one feature tag; extra tags allowed)
- Valid date format (YYYY-MM-DD)
- Valid related link format ([[wiki-link]])
"""

from __future__ import annotations

import re
from dataclasses import replace
from typing import TYPE_CHECKING

from ...core.helpers import atomic_write
from ..parser import parse_vault_metadata, rerender_frontmatter, split_frontmatter
from ._base import (
    CheckDiagnostic,
    CheckResult,
    Severity,
    VaultSnapshot,
    extract_feature_tags,
)

if TYPE_CHECKING:
    from pathlib import Path

    from ..models import DocType, DocumentMetadata

__all__ = ["check_frontmatter"]


def _read_source_text(doc_path: Path) -> tuple[str, str] | None:
    """Return ``(lf_content, source_newline)`` for *doc_path*, or None.

    Reads as bytes so the source CRLF/LF convention is observable;
    ``read_text`` collapses everything to ``\\n`` via universal newlines,
    which would silently strip CRLF before we ever see it and bake LF back
    into a previously-CRLF file. The content is normalized to LF for the
    regex/manipulation passes; the caller restores the source newline
    convention on the rendered output so files that arrived as CRLF leave
    as CRLF.
    """
    try:
        raw_content = doc_path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    source_newline = "\r\n" if "\r\n" in raw_content else "\n"
    return raw_content.replace("\r\n", "\n"), source_newline


def _normalized_tags(
    metadata: DocumentMetadata, yaml_block: str, doc_type: DocType | None
) -> tuple[list[str], bool, str | None]:
    """Normalize ``#`` prefixes, or construct tags from a bare ``feature:``.

    Returns the tag list, whether it differs from the parsed tags, and the
    fix description to record (``None`` when nothing changed).
    """
    new_tags = [tag if tag.startswith("#") else f"#{tag}" for tag in metadata.tags]
    if metadata.tags:
        if new_tags == list(metadata.tags):
            return new_tags, False, None
        return new_tags, True, "normalized tag # prefixes"

    feature_match = re.search(r"^feature:\s*(.+)$", yaml_block, re.MULTILINE)
    if not feature_match or not doc_type:
        return new_tags, False, None

    feature_val = feature_match.group(1).strip().strip("\"'")
    if not feature_val.startswith("#"):
        feature_val = f"#{feature_val}"
    return [doc_type.tag, feature_val], True, "constructed tags from feature field"


def _normalized_date(date_val: str | None) -> tuple[str | None, bool]:
    """Trim a date value down to its leading ``YYYY-MM-DD`` component."""
    if not date_val:
        return date_val, False
    date_str = str(date_val).strip()
    date_match = re.match(r"^(\d{4}-\d{2}-\d{2})", date_str)
    if not date_match or date_str == date_match.group(1):
        return date_val, False
    return date_match.group(1), True


def _existing_tag_lines(yaml_block: str) -> list[str]:
    """Return the verbatim ``tags:`` lines already present in *yaml_block*."""
    lines: list[str] = []
    for line in yaml_block.split("\n"):
        stripped = line.strip()
        if stripped.startswith("tags") or (
            stripped.startswith("-") and "#" in stripped
        ):
            lines.append(line)
    return lines


def _repair_frontmatter(
    content: str, doc_type: DocType | None
) -> tuple[str, list[str]] | None:
    """Return *content* with its frontmatter repaired, and the fixes applied.

    Normalizes tag ``#`` prefixes (or builds tags from a bare ``feature:``)
    and trims the date to ``YYYY-MM-DD``, then re-renders the frontmatter in
    canonical field order.

    Args:
        content: The ``\\n``-normalised document text.
        doc_type: The document's type, which supplies its directory tag.

    Returns:
        ``(repaired_content, fixes)``, or ``None`` when the document has no
        frontmatter or needs no fix.
    """
    split = split_frontmatter(content)
    if split.yaml_block is None:
        return None
    metadata, _ = parse_vault_metadata(content)
    fixes: list[str] = []

    # Fix 1 and 2: normalize tag prefixes, or construct tags from feature:
    new_tags, tags_changed, tag_fix = _normalized_tags(
        metadata, split.yaml_block, doc_type
    )
    if tag_fix:
        fixes.append(tag_fix)

    # Fix 3: Date format normalization
    date_val, date_fixed = _normalized_date(metadata.date)
    if date_fixed:
        fixes.append("normalized date format")

    if not fixes:
        return None

    # With no tags to write and none constructed, the tags lines already in
    # the frontmatter are kept as they are.
    keep_tag_lines = not new_tags and not tags_changed
    rendered = rerender_frontmatter(
        content,
        replace(metadata, tags=new_tags, date=date_val or metadata.date),
        render_stamps=True,
        quote_date=False,
        tag_lines=_existing_tag_lines(split.yaml_block) if keep_tag_lines else None,
    )
    return (rendered, fixes) if rendered is not None else None


def _fix_frontmatter(doc_path: Path, root_dir: Path) -> str | None:
    """Attempt to fix common frontmatter issues. Returns fix description or None.

    The read, the recomposition, and the write all run inside *doc_path*'s
    per-document advisory lock, so the frontmatter this pass rewrites is the
    frontmatter it actually read. Composing outside the lock would let a
    concurrent ``vault edit`` land between the read and the write, and the
    replacement - individually atomic, derived from bytes that no longer
    exist - would silently discard that edit.
    """
    from ..edit_engine import document_write_lock

    with document_write_lock(doc_path, root_dir):
        return _fix_frontmatter_locked(doc_path, root_dir)


def _fix_frontmatter_locked(doc_path: Path, root_dir: Path) -> str | None:
    """Recompose and rewrite *doc_path*'s frontmatter under its held lock.

    Args:
        doc_path: The document being fixed; its per-document lock is already
            held by :func:`_fix_frontmatter`.
        root_dir: Project root, used to derive the document's type.

    Returns:
        A ``"; "``-joined description of the fixes applied, or ``None`` when
        the document is unreadable, carries no frontmatter fence, or needs
        no fix.
    """
    from ..scanner import get_doc_type

    source = _read_source_text(doc_path)
    if source is None:
        return None
    content, source_newline = source

    repaired = _repair_frontmatter(content, get_doc_type(doc_path, root_dir))
    if repaired is None:
        return None
    rendered, fixes_applied = repaired
    # Restore the source file's newline convention. Internal LFs that
    # came from the body group also need promoting so the file does
    # not end up with mixed endings. ``atomic_write`` writes bytes
    # (via ``Path.write_bytes`` of the UTF-8-encoded payload), so the
    # ``\r\n`` sequences below land on disk byte-for-byte; switching to
    # ``Path.write_text`` would re-enable Python's universal-newline
    # translation on Windows and corrupt CRLF runs into ``\r\r\n``.
    new_content = (
        rendered if source_newline == "\n" else rendered.replace("\n", source_newline)
    )
    atomic_write(doc_path, new_content)
    return "; ".join(fixes_applied)


def check_frontmatter(
    root_dir: Path,
    *,
    snapshot: VaultSnapshot,
    feature: str | None = None,
    doc_type_filter: str | None = None,
    fix: bool = False,
) -> CheckResult:
    """Validate frontmatter of all vault documents.

    Enforces :meth:`~vaultspec_core.vaultcore.models.DocumentMetadata.validate`
    rules: at least two tags (one directory, one feature; extras allowed),
    valid ISO 8601 date, and ``[[wiki-link]]`` format for ``related`` entries.

    Args:
        root_dir: Project root directory.
        snapshot: Pre-built snapshot mapping document paths to parsed data.
        feature: Restrict checks to documents with this feature tag
            (without ``#``).
        doc_type_filter: Restrict checks to documents of this type
            (e.g. ``"adr"``).
        fix: When ``True``, attempt to auto-correct tag prefixes,
            reconstruct tags from a bare ``feature:`` field, and
            normalize date formats.

    Returns:
        :class:`~vaultspec_core.vaultcore.checks._base.CheckResult` with
        check name ``"frontmatter"``.
    """
    from ..scanner import get_doc_type

    result = CheckResult(check_name="frontmatter", supports_fix=True)

    for doc_path, (metadata, _body) in snapshot.items():
        # Indexes used to carry a non-standard one-tag frontmatter and
        # were exempted here; post-#91 they carry the standard two-tag
        # shape (``#index`` directory tag plus the feature tag) and run
        # through the same validator as every other document. The ADR
        # commits to "no more exemptions" at the frontmatter layer.
        if doc_type_filter:
            dt = get_doc_type(doc_path, root_dir)
            if dt and dt.value != doc_type_filter:
                continue

        if feature:
            feat = feature.lstrip("#")
            if feat not in extract_feature_tags(metadata.tags):
                continue

        errors = metadata.validate()
        if not errors:
            continue

        rel_path = doc_path.relative_to(root_dir)

        if fix:
            fix_desc = _fix_frontmatter(doc_path, root_dir)
            if fix_desc:
                result.fixed_count += 1
                result.diagnostics.append(
                    CheckDiagnostic(
                        path=rel_path,
                        message=f"Fixed: {fix_desc}",
                        severity=Severity.INFO,
                    )
                )
                new_content = doc_path.read_text(encoding="utf-8")
                new_metadata, _ = parse_vault_metadata(new_content)
                remaining_errors = new_metadata.validate()
                for msg in remaining_errors:
                    severity = (
                        Severity.ERROR
                        if "required" in msg.lower()
                        else Severity.WARNING
                    )
                    result.diagnostics.append(
                        CheckDiagnostic(
                            path=rel_path,
                            message=msg,
                            severity=severity,
                        )
                    )
                continue

        for msg in errors:
            severity = Severity.ERROR if "required" in msg.lower() else Severity.WARNING
            result.diagnostics.append(
                CheckDiagnostic(
                    path=rel_path,
                    message=msg,
                    severity=severity,
                    fixable=True,
                )
            )

    return result
