"""Check and optionally fix markdown hygiene in vault documents.

Three safe, idempotent lints aligned with markdownlint:

- MD009: no trailing whitespace on a line;
- MD012: no run of consecutive blank lines (collapsed to one);
- MD047: the file ends in exactly one newline.

Fenced code blocks are protected: trailing whitespace and blank-line runs
inside a fence may be significant, so they are left untouched. Riskier
transforms (tab conversion, reflow, heading spacing) are deliberately
omitted to keep ``--fix`` strictly safe. The fixer preserves the source
CRLF/LF newline convention and writes atomically, matching the discipline
of the ``frontmatter`` and ``annotations`` checkers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ...core.helpers import atomic_write
from ._base import (
    CheckDiagnostic,
    CheckResult,
    Severity,
    extract_feature_tags,
)

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["apply_markdown_hygiene", "check_markdown"]


@dataclass
class MarkdownStats:
    """Counts of markdown hygiene issues found (or fixed) in a document.

    Attributes:
        trailing_whitespace: Lines carrying trailing spaces or tabs (MD009).
        blank_runs: Blank lines removed when collapsing consecutive blank
            runs to a single blank line (MD012).
        final_newline: ``True`` when the trailing-newline convention was off
            (missing, absent, or doubled) (MD047).
    """

    trailing_whitespace: int = 0
    blank_runs: int = 0
    final_newline: bool = False

    @property
    def total(self) -> int:
        """Total number of distinct hygiene issues."""
        return self.trailing_whitespace + self.blank_runs + int(self.final_newline)

    def describe(self) -> str:
        """Return a compact human-readable summary of the issues."""
        parts = []
        if self.trailing_whitespace:
            suffix = "s" if self.trailing_whitespace != 1 else ""
            parts.append(f"{self.trailing_whitespace} trailing-whitespace line{suffix}")
        if self.blank_runs:
            suffix = "s" if self.blank_runs != 1 else ""
            parts.append(f"{self.blank_runs} extra blank line{suffix}")
        if self.final_newline:
            parts.append("final-newline fix")
        return ", ".join(parts) if parts else "no markdown issues"


def _is_fence(line: str) -> bool:
    """Return ``True`` if *line* opens or closes a fenced code block."""
    stripped = line.lstrip()
    return stripped.startswith("```") or stripped.startswith("~~~")


def apply_markdown_hygiene(content: str) -> tuple[str, MarkdownStats]:
    """Apply the markdown hygiene lints to LF-normalised *content*.

    Strips trailing whitespace outside fenced code blocks (MD009), collapses
    runs of consecutive blank lines outside fences to a single blank line
    (MD012), and ensures the result ends in exactly one newline (MD047). The
    transform is idempotent: applying it to its own output is a no-op.

    Args:
        content: Document content with ``\\n`` line endings.

    Returns:
        A ``(cleaned, stats)`` tuple where ``cleaned`` is the hygienic content
        and ``stats`` records what changed.
    """
    stats = MarkdownStats()
    lines = content.split("\n")

    # Tag each line with whether it sits strictly inside a fenced block. The
    # fence open/close markers themselves are treated as outside the fence
    # (they are never blank and their trailing whitespace is safe to strip).
    rows: list[list] = []
    in_fence = False
    for line in lines:
        if _is_fence(line):
            rows.append([line, False])
            in_fence = not in_fence
        else:
            rows.append([line, in_fence])

    # MD009: strip trailing whitespace outside fences.
    for row in rows:
        if not row[1]:
            trimmed = row[0].rstrip(" \t")
            if trimmed != row[0]:
                stats.trailing_whitespace += 1
                row[0] = trimmed

    # MD012: collapse consecutive blank lines outside fences.
    collapsed: list[str] = []
    prev_blank = False
    for text, fenced in rows:
        is_blank = (not fenced) and text == ""
        if is_blank and prev_blank:
            stats.blank_runs += 1
            continue
        collapsed.append(text)
        prev_blank = is_blank

    result = "\n".join(collapsed)

    # MD047: exactly one trailing newline (leave a wholly blank doc alone).
    normalized = result.rstrip("\n")
    if normalized:
        desired = normalized + "\n"
        if desired != result:
            stats.final_newline = True
            result = desired

    return result, stats


def check_markdown(
    root_dir: Path,
    *,
    feature: str | None = None,
    fix: bool = False,
) -> CheckResult:
    """Check and optionally fix markdown hygiene across vault documents.

    Applies the MD009 / MD012 / MD047 lints (see
    :func:`apply_markdown_hygiene`). Without ``--fix`` each affected document
    yields one ``WARNING`` describing the issues; with ``--fix`` the document
    is rewritten in place, preserving its CRLF/LF newline convention, and an
    ``INFO`` diagnostic records the repair.

    Args:
        root_dir: Project root directory.
        feature: Restrict checks to documents with this feature tag
            (without ``#``).
        fix: When ``True``, rewrite affected documents in place.

    Returns:
        :class:`~vaultspec_core.vaultcore.checks._base.CheckResult` with
        check name ``"markdown"``.
    """
    from ..parser import parse_vault_metadata
    from ..scanner import scan_vault

    result = CheckResult(check_name="markdown", supports_fix=True)
    wanted_feature = feature.lstrip("#") if feature else None

    for doc_path in scan_vault(root_dir):
        try:
            raw_content = doc_path.read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        metadata, _body = parse_vault_metadata(raw_content)
        if wanted_feature and wanted_feature not in extract_feature_tags(metadata.tags):
            continue

        source_newline = "\r\n" if "\r\n" in raw_content else "\n"
        content_lf = raw_content.replace("\r\n", "\n")
        cleaned_lf, stats = apply_markdown_hygiene(content_lf)
        if stats.total == 0:
            continue

        rel_path = doc_path.relative_to(root_dir)

        if fix:
            cleaned = (
                cleaned_lf
                if source_newline == "\n"
                else cleaned_lf.replace("\n", source_newline)
            )
            atomic_write(doc_path, cleaned)
            result.fixed_count += 1
            result.diagnostics.append(
                CheckDiagnostic(
                    path=rel_path,
                    message=f"Fixed markdown hygiene: {stats.describe()}",
                    severity=Severity.INFO,
                )
            )
            continue

        result.diagnostics.append(
            CheckDiagnostic(
                path=rel_path,
                message=f"Markdown hygiene issues: {stats.describe()}",
                severity=Severity.WARNING,
                fixable=True,
                fix_description="Run markdown check with --fix to repair them",
            )
        )

    return result
