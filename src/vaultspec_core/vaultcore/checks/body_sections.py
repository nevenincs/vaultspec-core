"""Validate a document body against the sections its template mandates.

The shipped templates in ``.vaultspec/templates/`` are the single source of
truth for a document type's required sections: each template carries a fixed
set of level-two (``## ``) headings that constitute the body contract. Nothing
previously confirmed a document actually kept them - an ADR could ship without
its ``Consequences`` section and pass every check.

This checker derives the required sections per document type by extracting the
``## `` headings from that type's template (never a hardcoded list), then for
each document verifies every required heading is present and carries real
authored content. A required section that is absent, or that holds only a
scaffold hint-comment or an unreplaced ``{placeholder}``, is reported: a
scaffolded-but-unauthored document cannot satisfy the contract. Author-added
extra sections are ignored; only the absence or emptiness of a required
section is a finding.

Edge handling:

- Execution records select ``exec-step.md`` or ``exec-summary.md`` by the
  ``-summary`` filename convention.
- Generated feature indexes are out of scope (their body is machine-authored).
- A document type with no template, or a template that cannot be read, degrades
  to a skip (no finding) rather than a crash (No-Crash policy).

The checker is read-only: a section's position, ordering, and content are the
author's, so no safe automatic repair exists. Each finding's ``fix_description``
names the manual remedy.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from ._base import (
    CheckDiagnostic,
    CheckResult,
    Severity,
    extract_feature_tags,
    is_generated_index,
)

if TYPE_CHECKING:
    from pathlib import Path

    from ._base import VaultSnapshot

logger = logging.getLogger(__name__)

__all__ = ["check_body_sections"]

#: A level-two heading line (``## Title``), excluding deeper ``### `` headings.
_H2_RE = re.compile(r"^##[ \t]+(?P<title>\S.*?)\s*$", re.MULTILINE)

#: An HTML comment block, stripped before content-emptiness is judged.
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)

#: Content consisting only of ``{placeholder}`` tokens and whitespace, treated
#: as empty so an unauthored scaffold section does not satisfy the contract.
_PLACEHOLDER_ONLY_RE = re.compile(r"^(?:\s*\{[^{}]*\}\s*)+$")


def _required_sections(template_text: str) -> list[str]:
    """Return the ordered ``## `` section titles a template mandates.

    HTML comment blocks (which embed example headings in the scaffold hints)
    are stripped first so only the template's real headings are extracted.
    """
    stripped = _COMMENT_RE.sub("", template_text)
    return [m.group("title") for m in _H2_RE.finditer(stripped)]


def _section_contents(body: str) -> dict[str, str]:
    """Map each ``## `` heading title in *body* to its raw content.

    Content runs from just after the heading line to the next ``## `` heading
    or the end of the document. A later duplicate heading overwrites an earlier
    one; documents do not legitimately repeat a required section.
    """
    contents: dict[str, str] = {}
    matches = list(_H2_RE.finditer(body))
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        contents[match.group("title")] = body[start:end]
    return contents


def _is_empty(section_body: str) -> bool:
    """Return ``True`` when a section carries no real authored content.

    A section is empty when, after HTML comments are stripped, nothing but
    whitespace remains, or when the remainder is only ``{placeholder}`` tokens.
    """
    text = _COMMENT_RE.sub("", section_body).strip()
    if not text:
        return True
    return _PLACEHOLDER_ONLY_RE.fullmatch(text) is not None


def check_body_sections(
    root_dir: Path,
    *,
    snapshot: VaultSnapshot,
    feature: str | None = None,
) -> CheckResult:
    """Validate every document body carries its template-mandated sections.

    Args:
        root_dir: Project root directory.
        snapshot: Pre-built snapshot mapping document paths to parsed
            ``(metadata, body)`` tuples.
        feature: Restrict checks to documents carrying this feature tag
            (without ``#``).

    Returns:
        :class:`~vaultspec_core.vaultcore.checks._base.CheckResult` with check
        name ``"body-sections"``. Does not support ``--fix``.
    """
    from ..hydration import get_template_path
    from ..scanner import get_doc_type

    result = CheckResult(check_name="body-sections", supports_fix=False)

    # Cache required-section lists per (doc_type, summary) so each template is
    # read and parsed once per run rather than once per document.
    required_cache: dict[tuple[str, bool], list[str] | None] = {}

    for doc_path, (metadata, body) in sorted(snapshot.items()):
        doc_type = get_doc_type(doc_path, root_dir)
        if doc_type is None:
            continue
        if is_generated_index(doc_path):
            continue
        if feature:
            feat = feature.lstrip("#")
            if feat not in extract_feature_tags(metadata.tags):
                continue

        is_summary = doc_path.stem.endswith("-summary")
        cache_key = (doc_type.value, is_summary)
        if cache_key not in required_cache:
            template_path = get_template_path(root_dir, doc_type, summary=is_summary)
            if template_path is None:
                required_cache[cache_key] = None
            else:
                try:
                    template_text = template_path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    required_cache[cache_key] = None
                else:
                    required_cache[cache_key] = _required_sections(template_text)

        required = required_cache[cache_key]
        if not required:
            # No template mapping, unreadable template, or a template with no
            # required sections: nothing to validate against, skip cleanly.
            continue

        rel_path = doc_path.relative_to(root_dir)
        contents = _section_contents(body)

        for title in required:
            if title not in contents:
                result.diagnostics.append(
                    CheckDiagnostic(
                        path=rel_path,
                        message=(
                            f"Missing required section '## {title}' mandated by "
                            f"the {doc_type.value} template."
                        ),
                        severity=Severity.WARNING,
                        fixable=False,
                        fix_description=f"Add and fill the '## {title}' section.",
                    )
                )
            elif _is_empty(contents[title]):
                result.diagnostics.append(
                    CheckDiagnostic(
                        path=rel_path,
                        message=(
                            f"Required section '## {title}' is empty (only "
                            "scaffold comments or placeholders)."
                        ),
                        severity=Severity.WARNING,
                        fixable=False,
                        fix_description=f"Author real content under '## {title}'.",
                    )
                )

    return result
