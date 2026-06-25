"""Check for unreplaced ``{...}`` template placeholders in document body prose.

Every shipped template seeds curly-brace placeholders (``{feature}``,
``{topic}``, the ``{proposed|accepted|rejected|deprecated}`` enum, and so
on). The framework rule requires that no document is committed with a
placeholder remaining. This checker enforces that rule for body prose.

Frontmatter placeholders are out of scope: a literal ``#{feature}`` tag or a
``{yyyy-mm-dd}`` date already fails the ``frontmatter`` validator, and
placeholders inside ``<!-- -->`` template guidance are removed by the
``annotations`` checker. To avoid double-reporting that residue, HTML
comments are stripped before scanning. Detection only - an unreplaced
placeholder marks missing author or machine content that cannot be
synthesised safely (parity with ``body-links``).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ._base import (
    CheckDiagnostic,
    CheckResult,
    Severity,
    VaultSnapshot,
    extract_feature_tags,
)

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["KNOWN_PLACEHOLDERS", "check_placeholders", "is_template_placeholder"]

# Candidate-token grammar: lowercase ASCII letters plus ``0-9 _ - * |``, with
# at least one letter, and no spaces, quotes, or colons. This admits every
# template placeholder while rejecting most incidental brace usage up front:
# JSON / dict literals ({ "key": 1 } - spaces and colons), regex quantifiers
# ({4}, {2,4} - no letter), shell expansions (${VAR}), and doubled-brace
# escapes ({{feature}}) - the lookbehind rejects a leading $ or {, the
# lookahead rejects a trailing }. It is only a first filter; a candidate is
# residue only if it also matches the known template vocabulary below.
_PLACEHOLDER_RE = re.compile(r"(?<![${])\{[a-z0-9_*|-]*[a-z][a-z0-9_*|-]*\}(?!\})")

# The vocabulary the shipped templates actually seed. A bare ``{...}`` token in
# body prose is residue only if its inner name is one of these (or a date form,
# or an enum - see is_template_placeholder). Restricting to this set avoids
# flagging authored references to runtime variables that happen to use the same
# brace syntax (``{path}``, ``{exc}``, ``{provider}`` in an f-string described
# in prose). Kept in sync with builtins/templates by a drift test.
KNOWN_PLACEHOLDERS = frozenset(
    {
        "feature",
        "topic",
        "title",
        "phase",
        "wave",
        "step",
        "tier",
        "summary",
        "level",
        "description",
        "research",
        "reference",
        "adr",
        "heading",
        "plan_stem",
        "step_id",
        "scope_block",
        "document_list",
        "file1",
        "file2",
    }
)

# Fenced code blocks (``` or ~~~, with optional language tag) carry literal
# brace usage (JSON, shell, config) that is not template residue.
_CODE_FENCE_RE = re.compile(
    r"^(?:```|~~~)[^\n]*\n.*?^(?:```|~~~)\s*$",
    re.MULTILINE | re.DOTALL,
)

# HTML comments (<!-- ... -->): placeholders here are template guidance and
# are removed by the annotations checker; strip them to avoid double-reporting.
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)

# Inline code spans, including multi-backtick spans that themselves contain
# single backticks (the ``# `{feature}` plan`` heading is documented in prose
# as ``# `{feature}` plan``). The backreference matches the same run length.
_INLINE_CODE_RE = re.compile(r"(`+)(.+?)\1", re.DOTALL)

# ATX headings (#, up to 3 leading spaces of indent, 1-6 hashes).
_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s")


def is_template_placeholder(token: str) -> bool:
    """Return ``True`` if *token* is residue from a shipped template.

    A token is residue when it is an enum choice (contains ``|``, e.g.
    ``{proposed|accepted|rejected|deprecated}``), a date form
    (``{yyyy-mm-dd...}``), or its inner name is in :data:`KNOWN_PLACEHOLDERS`.

    Args:
        token: A candidate ``{...}`` token including its braces.

    Returns:
        ``True`` when the token is a known template placeholder.
    """
    inner = token[1:-1]
    if "|" in inner:
        return True
    if inner.startswith("yyyy-mm-dd"):
        return True
    return inner in KNOWN_PLACEHOLDERS


def _strip_non_prose(body: str) -> str:
    """Remove non-prose regions that legitimately contain ``{...}`` braces.

    Fenced code blocks and HTML comments are removed wholesale. Inline code
    spans are stripped only on non-heading lines: a placeholder wrapped in
    backticks in body prose is documentation (an f-string field, a literal
    ``#{feature}`` tag form), not residue. The one place a real placeholder is
    legitimately backtick-wrapped is a heading title (the shipped
    ``# `{feature}` plan`` form), so inline code on heading lines is kept.

    Args:
        body: Document body text (everything after the frontmatter).

    Returns:
        Body text with non-prose brace regions removed.
    """
    stripped = _CODE_FENCE_RE.sub("", body)
    stripped = _HTML_COMMENT_RE.sub("", stripped)
    out_lines = []
    for line in stripped.split("\n"):
        if _HEADING_RE.match(line):
            out_lines.append(line)
        else:
            out_lines.append(_INLINE_CODE_RE.sub("", line))
    return "\n".join(out_lines)


def check_placeholders(
    root_dir: Path,
    *,
    snapshot: VaultSnapshot,
    feature: str | None = None,
) -> CheckResult:
    """Find unreplaced ``{...}`` template placeholders in document body prose.

    Scans the body (everything after the YAML frontmatter) after stripping
    fenced code blocks and HTML comments, and inline code spans on non-heading
    lines (see :func:`_strip_non_prose`). Only tokens matching the known
    template vocabulary (:func:`is_template_placeholder`) are reported, each as
    an ``ERROR``. A placeholder containing a
    ``|`` is an enum choice (e.g. ``{proposed|accepted|rejected|deprecated}``)
    and is reported as a "choose one option" finding rather than a missing
    value. Frontmatter is not scanned - leftover frontmatter placeholders are
    already caught by the ``frontmatter`` validator.

    Args:
        root_dir: Project root directory.
        snapshot: Pre-built snapshot mapping document paths to parsed data.
        feature: Restrict checks to documents with this feature tag
            (without ``#``).

    Returns:
        :class:`~vaultspec_core.vaultcore.checks._base.CheckResult` with
        check name ``"placeholders"``.
    """
    result = CheckResult(check_name="placeholders", supports_fix=False)

    for doc_path, (metadata, body) in snapshot.items():
        if feature:
            feat = feature.lstrip("#")
            if feat not in extract_feature_tags(metadata.tags):
                continue

        rel_path = doc_path.relative_to(root_dir)
        prose = _strip_non_prose(body)

        for match in _PLACEHOLDER_RE.finditer(prose):
            token = match.group(0)
            if not is_template_placeholder(token):
                continue
            if "|" in token:
                options = token[1:-1].replace("|", ", ")
                message = (
                    f"Unresolved template enum {token} - choose one option "
                    f"({options}) and replace it"
                )
            else:
                message = (
                    f"Unreplaced template placeholder {token} - replace it with "
                    "the intended value before committing"
                )
            result.diagnostics.append(
                CheckDiagnostic(
                    path=rel_path,
                    message=message,
                    severity=Severity.ERROR,
                )
            )

    return result
