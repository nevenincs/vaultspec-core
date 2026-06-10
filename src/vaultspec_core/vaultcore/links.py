"""Extract wiki-link relationships from vault documents.

This module provides focused helpers for reading internal links from markdown
bodies and `related:` frontmatter fields. It exists to keep vault link parsing
narrow, reusable, and separate from broader metadata parsing.
"""

from __future__ import annotations

import logging
import re
from collections import Counter

__all__ = ["extract_related_links", "extract_wiki_links"]

logger = logging.getLogger(__name__)


_CODE_FENCE_RE = re.compile(
    r"^(?:```|~~~)[^\n]*\n.*?^(?:```|~~~)\s*$",
    re.MULTILINE | re.DOTALL,
)
_INLINE_CODE_RE = re.compile(r"`[^`]+`")
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def _strip_non_prose(text: str) -> str:
    """Remove code blocks, inline code, and HTML comments from text."""
    stripped = _CODE_FENCE_RE.sub("", text)
    stripped = _HTML_COMMENT_RE.sub("", stripped)
    return _INLINE_CODE_RE.sub("", stripped)


def extract_wiki_links(content: str) -> Counter[str]:
    """Extract all ``[[wiki-link]]`` targets from a markdown string.

    Handles both ``[[Target]]`` and ``[[Target|Display]]`` forms; only the
    target (left-hand) portion is counted.  Links inside fenced code blocks
    and inline code spans are ignored.

    Multiplicity is preserved: a body that cites the same target three times
    yields a count of ``3`` for that target.  The returned
    :class:`~collections.Counter` is a ``dict`` subclass, so iterating it
    yields target keys and ``in`` membership tests behave like a set, while
    indexing recovers the per-target count.

    Args:
        content: Raw markdown text to scan.

    Returns:
        :class:`~collections.Counter` mapping each unique link target string
        (whitespace-stripped) to the number of times it appears.
    """
    # Strip code blocks/spans/comments so TOML [[headers]] etc. aren't matched
    prose = _strip_non_prose(content)

    # Matches [[Link Name]] or [[Link Name|Display Name]]
    pattern = r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]"
    matches = re.findall(pattern, prose)
    counts: Counter[str] = Counter()
    for m in matches:
        target = m.strip()
        # Tolerate .md extensions (Obsidian convention: [[note-name]] without extension)
        if target.endswith(".md"):
            target = target[:-3]
        counts[target] += 1
    return counts


def extract_related_links(related: list[str]) -> Counter[str]:
    """Extract link targets from the ``related`` YAML frontmatter field.

    Each entry is expected to be a ``[[wiki-link]]`` string.  Malformed
    entries are logged and skipped.

    Multiplicity is preserved: if the same target is listed twice in the
    ``related`` field it carries a count of ``2``.  The returned
    :class:`~collections.Counter` is a ``dict`` subclass, so callers that
    only need membership can iterate keys while callers that need edge
    weight can read the count.

    Args:
        related: List of raw ``related`` values from parsed frontmatter.

    Returns:
        :class:`~collections.Counter` mapping each resolved link target to
        the number of times it appears in the ``related`` field.
    """
    links: Counter[str] = Counter()
    malformed_count = 0

    if not related:
        return links

    # Flatten nested lists produced by some YAML parsers
    flat: list[str] = []
    for item in related:
        if isinstance(item, list):
            flat.extend(str(v) for v in item if v)
        else:
            flat.append(item)

    for link in flat:
        # related links are expected to be [[Link Name]]
        match = re.match(r"^\[\[([^\]|]+)(?:\|[^\]]+)?\]\]$", link)
        if match:
            target = match.group(1).strip()
            # Strip .md (Obsidian wiki-link convention)
            if target.endswith(".md"):
                target = target[:-3]
            links[target] += 1
        else:
            malformed_count += 1
            logger.debug("Malformed related link: %s", link)
    if malformed_count > 0:
        logger.warning("Found %d malformed links in related field", malformed_count)
    return links
