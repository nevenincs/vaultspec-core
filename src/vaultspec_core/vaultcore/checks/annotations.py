"""Check and strip generated template annotations from vault documents."""

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

__all__ = ["AnnotationStats", "check_annotations", "strip_template_annotations"]


@dataclass(frozen=True)
class AnnotationStats:
    """Counts of annotation syntaxes removed from a vault document."""

    frontmatter_comments: int = 0
    html_comments: int = 0

    @property
    def total(self) -> int:
        """Return total annotations found."""
        return self.frontmatter_comments + self.html_comments

    def describe(self) -> str:
        """Return a compact human-readable annotation count."""
        parts: list[str] = []
        if self.frontmatter_comments:
            suffix = "" if self.frontmatter_comments == 1 else "s"
            parts.append(
                f"{self.frontmatter_comments} frontmatter comment line{suffix}"
            )
        if self.html_comments:
            suffix = "" if self.html_comments == 1 else "s"
            parts.append(f"{self.html_comments} HTML comment block{suffix}")
        return ", ".join(parts) if parts else "no annotations"


def strip_template_annotations(content: str) -> tuple[str, AnnotationStats]:
    """Remove agent-facing template annotations from a rendered document.

    The sanitizer is intentionally explicit-operation-only: template hydration
    leaves annotations intact for agents, while check and repair surfaces call
    this function only when the operator requests a fix.
    """
    normalized = content.replace("\r\n", "\n")
    frontmatter, body, has_frontmatter = _split_frontmatter(normalized)

    frontmatter_comment_count = 0
    if has_frontmatter:
        frontmatter, frontmatter_comment_count = _strip_frontmatter_comments(
            frontmatter
        )

    body, html_comment_count = _strip_html_comments(body)
    stats = AnnotationStats(
        frontmatter_comments=frontmatter_comment_count,
        html_comments=html_comment_count,
    )
    return frontmatter + body, stats


def check_annotations(
    root_dir: Path,
    *,
    feature: str | None = None,
    fix: bool = False,
) -> CheckResult:
    """Find or remove template annotations from vault documents.

    Args:
        root_dir: Project root directory.
        feature: Restrict checks to documents with this feature tag.
        fix: When ``True``, remove YAML comment-only frontmatter lines and
            Markdown HTML comment blocks from matching documents.

    Returns:
        :class:`~vaultspec_core.vaultcore.checks._base.CheckResult` with check
        name ``"annotations"``.
    """
    from ..parser import parse_vault_metadata
    from ..scanner import scan_vault

    result = CheckResult(check_name="annotations", supports_fix=True)
    wanted_feature = feature.lstrip("#") if feature else None

    for doc_path in scan_vault(root_dir):
        try:
            raw = doc_path.read_bytes()
            raw_content = raw.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        metadata, _body = parse_vault_metadata(raw_content)
        if wanted_feature and wanted_feature not in extract_feature_tags(metadata.tags):
            continue

        source_newline = "\r\n" if "\r\n" in raw_content else "\n"
        cleaned_lf, stats = strip_template_annotations(raw_content)
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
                    message=f"Removed template annotations: {stats.describe()}",
                    severity=Severity.INFO,
                )
            )
            continue

        result.diagnostics.append(
            CheckDiagnostic(
                path=rel_path,
                message=f"Template annotations remain: {stats.describe()}",
                severity=Severity.WARNING,
                fixable=True,
                fix_description="Run annotations check with --fix to strip them",
            )
        )

    return result


def _split_frontmatter(content: str) -> tuple[str, str, bool]:
    if not content.startswith("---\n"):
        return "", content, False

    lines = content.splitlines(keepends=True)
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            split_at = index + 1
            return "".join(lines[:split_at]), "".join(lines[split_at:]), True
    return "", content, False


def _strip_frontmatter_comments(frontmatter: str) -> tuple[str, int]:
    lines = frontmatter.splitlines(keepends=True)
    kept: list[str] = []
    removed = 0
    for line in lines:
        if line.lstrip().startswith("#"):
            removed += 1
            continue
        kept.append(line)
    return "".join(kept), removed


def _strip_html_comments(markdown: str) -> tuple[str, int]:
    lines = markdown.splitlines(keepends=True)
    output: list[str] = []
    removed = 0
    in_fence = False
    fence_marker: str | None = None
    in_comment = False

    for line in lines:
        stripped = line.lstrip()
        if not in_comment and (
            stripped.startswith("```") or stripped.startswith("~~~")
        ):
            marker = stripped[:3]
            if not in_fence:
                in_fence = True
                fence_marker = marker
            elif marker == fence_marker:
                in_fence = False
                fence_marker = None
            output.append(line)
            continue

        if in_fence:
            output.append(line)
            continue

        if in_comment:
            end = line.find("-->")
            if end == -1:
                continue
            in_comment = False
            tail = line[end + 3 :]
            if tail.strip():
                output.append(tail)
            continue

        if not stripped.startswith("<!--"):
            output.append(line)
            continue

        comment_text = stripped[4:].lstrip()
        if comment_text.startswith("RETIRED:"):
            output.append(line)
            continue

        end = stripped.find("-->")
        if end == -1:
            removed += 1
            in_comment = True
            continue

        tail = stripped[end + 3 :]
        if tail.strip():
            output.append(line)
            continue

        removed += 1

    return "".join(output), removed
