"""Check for wiki-links and markdown links in document body text.

Body text is prose after the YAML frontmatter closing ``---``.  File
references in body should use backtick code spans, not links.  Wiki-links
belong exclusively in the ``related:`` frontmatter field.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ...core.helpers import atomic_write
from ..links import extract_wiki_links, rewrite_wiki_links_as_code_spans
from ._base import (
    CheckDiagnostic,
    CheckResult,
    Severity,
    VaultSnapshot,
    is_generated_index,
)

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["check_body_links"]

# [display](target) where target is NOT a URL or anchor
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((?!https?://|#|mailto:)([^)]+)\)")

# Fenced code blocks (``` or ~~~, with optional language tag)
_CODE_FENCE_RE = re.compile(
    r"^(?:```|~~~)[^\n]*\n.*?^(?:```|~~~)\s*$",
    re.MULTILINE | re.DOTALL,
)

# Inline code spans (`...`)
_INLINE_CODE_RE = re.compile(r"`[^`]+`")

# HTML comments (<!-- ... -->), may span multiple lines
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def _strip_non_prose(body: str) -> str:
    """Remove code blocks, inline code, and HTML comments from body."""
    stripped = _CODE_FENCE_RE.sub("", body)
    stripped = _HTML_COMMENT_RE.sub("", stripped)
    return _INLINE_CODE_RE.sub("", stripped)


def check_body_links(
    root_dir: Path,
    *,
    snapshot: VaultSnapshot,
    feature: str | None = None,
    fix: bool = False,
) -> CheckResult:
    """Find wiki-links and markdown path links in document body text.

    Detects ``[[wiki-link]]`` and ``[text](path)`` patterns in the body
    (everything after the YAML frontmatter ``---`` delimiter).  Links in
    ``related:`` frontmatter are not flagged.  Index files
    (``*.index.md``) are skipped because they legitimately list vault
    documents in body text as a generated inventory.

    Args:
        root_dir: Project root directory.
        snapshot: Pre-built snapshot mapping document paths to parsed data.
        feature: Restrict checks to documents with this feature tag
            (without ``#``).
        fix: When ``True``, rewrite prose wiki-links as backtick code spans.

    Returns:
        :class:`~vaultspec_core.vaultcore.checks._base.CheckResult` with
        check name ``"body-links"``.
    """
    from ..parser import parse_vault_metadata
    from ._base import extract_feature_tags

    result = CheckResult(check_name="body-links", supports_fix=True)

    for doc_path, (metadata, body) in snapshot.items():
        # Skip generated index files
        if is_generated_index(doc_path):
            continue

        if feature:
            feat = feature.lstrip("#")
            if feat not in extract_feature_tags(metadata.tags):
                continue

        rel_path = doc_path.relative_to(root_dir)

        # Strip code blocks and inline code before scanning
        prose = _strip_non_prose(body)

        wiki_links = extract_wiki_links(body)
        if fix and wiki_links:
            raw_content = doc_path.read_bytes().decode("utf-8")
            _metadata, raw_body = parse_vault_metadata(raw_content)
            fixed_body, replaced = rewrite_wiki_links_as_code_spans(raw_body)
            prefix = raw_content[: len(raw_content) - len(raw_body)]
            atomic_write(doc_path, prefix + fixed_body)
            result.fixed_count += 1
            result.diagnostics.append(
                CheckDiagnostic(
                    path=rel_path,
                    message=f"Fixed {replaced} body wiki-link(s) as code spans",
                    severity=Severity.INFO,
                )
            )
        else:
            for target, count in wiki_links.items():
                for _occurrence in range(count):
                    result.diagnostics.append(
                        CheckDiagnostic(
                            path=rel_path,
                            message=(
                                f"Wiki-link in body text: [[{target}]] "
                                "- move to related: frontmatter or use backtick "
                                "code span"
                            ),
                            severity=Severity.ERROR,
                            fixable=True,
                            fix_description=(
                                "Run body-links check with --fix to convert it "
                                "to a code span"
                            ),
                        )
                    )

        # Detect markdown path links in body
        for match in _MD_LINK_RE.finditer(prose):
            display = match.group(1)
            target = match.group(2)
            result.diagnostics.append(
                CheckDiagnostic(
                    path=rel_path,
                    message=(
                        f"Markdown link in body text: [{display}]({target}) "
                        "- use backtick code span for file references"
                    ),
                    severity=Severity.ERROR,
                )
            )

    return result
