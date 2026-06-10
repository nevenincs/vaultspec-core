"""CRLF-preserving, atomic related-frontmatter surgery helpers.

Provides two operations on the ``related:`` YAML field in vault document
frontmatter - :func:`remove_related_entries` and
:func:`append_related_entry` - without round-tripping the whole document
through a YAML dumper.  Both operations preserve the original line-ending
convention (CRLF or LF), write atomically via a temp-file rename, and
touch only the ``related:`` list block inside the YAML fence.

All callers that mutate ``related:`` frontmatter (the dangling-link fixer,
``vault link add``, ``vault link remove``) share this single implementation
so no drift can develop between them.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ..core.helpers import atomic_write

if TYPE_CHECKING:
    from pathlib import Path


__all__ = [
    "append_related_entry",
    "remove_related_entries",
]

# Matches a YAML list entry of the form:  - "[[some-target]]"
# Captures the inner stem (without the [[ ]] delimiters and optional quotes).
_RELATED_ENTRY_RE = re.compile(r'^\s*-\s*["\']?\[\[(.+?)\]\]["\']?\s*$')


def _read_preserve_newlines(path: Path) -> tuple[str, str]:
    """Read a file and return ``(normalised_content, original_newline)``.

    Args:
        path: Path to the UTF-8 encoded document.

    Returns:
        Tuple of the content with ``\\n``-normalised line endings and the
        detected newline string (``'\\r\\n'`` or ``'\\n'``).

    Raises:
        OSError: When the file cannot be read.
        UnicodeDecodeError: When the content is not valid UTF-8.
    """
    raw = path.read_bytes().decode("utf-8")
    newline = "\r\n" if "\r\n" in raw else "\n"
    return raw.replace("\r\n", "\n"), newline


def _atomic_write_restore(path: Path, content: str) -> None:
    """Write *content* to *path* atomically; restore from .bak on failure.

    A ``.bak`` copy of the original is written before the atomic write and
    removed on success.  If the write fails the original is restored from
    the ``.bak`` copy.

    Args:
        path: Destination file path.
        content: UTF-8 text to write; must already have the correct line
            endings applied before this call.

    Raises:
        Exception: Re-raises any exception from the underlying write after
            restoring the backup.
    """
    bak = path.with_suffix(path.suffix + ".bak")
    bak.write_bytes(path.read_bytes())
    try:
        atomic_write(path, content)
    except Exception:
        if bak.exists():
            bak.replace(path)
        raise
    bak.unlink(missing_ok=True)


def remove_related_entries(path: Path, targets: list[str]) -> int:
    """Remove ``[[target]]`` entries from the ``related:`` YAML field.

    Operates only on lines within the ``related:`` list block inside the
    YAML frontmatter.  Body wiki-links are never touched.  CRLF line
    endings are preserved byte-for-byte on the lines outside the modified
    block.

    When every entry under ``related:`` is removed the key is rewritten as
    ``related: []`` so the file remains valid YAML.

    Args:
        path: Absolute path to the vault document.
        targets: Stems (without ``[[ ]]``) to remove; comparison is
            case-insensitive.

    Returns:
        Number of entries actually removed (0 if none matched or the file
        could not be read).
    """
    try:
        content, source_newline = _read_preserve_newlines(path)
    except (OSError, UnicodeDecodeError):
        return 0

    lines = content.split("\n")
    target_set = {t.lower() for t in targets}

    in_frontmatter = False
    in_related = False
    related_idx: int | None = None
    new_lines: list[str] = []
    removed = 0

    for line in lines:
        if line.strip() == "---":
            if not in_frontmatter:
                in_frontmatter = True
            else:
                in_frontmatter = False
                in_related = False
            new_lines.append(line)
            continue

        if in_frontmatter:
            if line.startswith("related:"):
                in_related = True
                related_idx = len(new_lines)
                new_lines.append(line)
                continue

            # Exit the related block on any non-indented key
            if in_related and line and line[0] not in (" ", "\t"):
                in_related = False

            if in_related:
                m = _RELATED_ENTRY_RE.match(line)
                if m and m.group(1).lower() in target_set:
                    removed += 1
                    continue

        new_lines.append(line)

    if not removed:
        return 0

    # If all entries were removed, emit `related: []` so the YAML stays valid.
    if related_idx is not None:
        after_idx = related_idx + 1
        after = new_lines[after_idx] if after_idx < len(new_lines) else ""
        if not (after.startswith((" ", "\t")) and after.lstrip().startswith("-")):
            new_lines[related_idx] = "related: []"

    new_content = source_newline.join(new_lines)
    _atomic_write_restore(path, new_content)
    return removed


def append_related_entry(path: Path, wiki_link: str) -> bool:
    """Append a ``[[wiki_link]]`` entry to the ``related:`` YAML field.

    Appends the entry as ``  - '[[stem]]'`` at the end of the existing
    ``related:`` list block.  If no ``related:`` key exists, one is
    inserted before the closing ``---`` fence.  If the entry already
    exists (case-insensitive stem match) the file is left unchanged and
    ``False`` is returned.

    Only the ``related:`` frontmatter block is touched; body text is never
    modified.  CRLF line endings are preserved.

    Args:
        path: Absolute path to the vault document.
        wiki_link: The ``[[stem]]`` string to append.  Accepts both
            ``[[stem]]`` and bare-stem forms; normalised to
            ``'[[stem]]'`` on write.

    Returns:
        ``True`` when the entry was appended; ``False`` when the entry
        already existed (idempotent no-op).

    Raises:
        OSError: When the file cannot be read or written.
        UnicodeDecodeError: When the content is not valid UTF-8.
        ValueError: When *wiki_link* cannot be parsed to a stem.
    """
    # Normalise the target stem
    stem = _extract_stem(wiki_link)
    if not stem:
        raise ValueError(f"Cannot parse stem from wiki_link: {wiki_link!r}")

    content, source_newline = _read_preserve_newlines(path)
    lines = content.split("\n")

    in_frontmatter = False
    in_related = False
    related_idx: int | None = None
    last_related_item_idx: int | None = None
    frontmatter_close_idx: int | None = None

    for i, line in enumerate(lines):
        if line.strip() == "---":
            if not in_frontmatter:
                in_frontmatter = True
            else:
                in_frontmatter = False
                in_related = False
                frontmatter_close_idx = i
            continue

        if in_frontmatter:
            if line.startswith("related:"):
                in_related = True
                related_idx = i
                # Check if it's an inline form like `related: []`
                stripped = line[len("related:") :].strip()
                if stripped and stripped != "[]":
                    # unexpected inline value - treat as list start
                    pass
                continue

            if in_related:
                if line and line[0] not in (" ", "\t"):
                    # New top-level key; block ended
                    in_related = False
                else:
                    m = _RELATED_ENTRY_RE.match(line)
                    if m:
                        # Idempotency check
                        if m.group(1).lower() == stem.lower():
                            return False
                        last_related_item_idx = i

    # If entry not found (would have returned False above), we append it.
    new_entry = f"  - '[[{stem}]]'"

    new_lines = list(lines)

    if related_idx is not None:
        # Append after the last known related item, or right after the key
        insert_after = (
            last_related_item_idx if last_related_item_idx is not None else related_idx
        )
        # Handle the case where related: [] or related: (bare) exists
        key_line = lines[related_idx]
        stripped = key_line[len("related:") :].strip()
        if stripped in ("[]", ""):
            # Replace the key with a block-form key + new entry
            new_lines[related_idx] = "related:"
            new_lines.insert(related_idx + 1, new_entry)
        else:
            new_lines.insert(insert_after + 1, new_entry)
    elif frontmatter_close_idx is not None:
        # No related: key found - insert one before the closing ---
        new_lines.insert(frontmatter_close_idx, new_entry)
        new_lines.insert(frontmatter_close_idx, "related:")
    else:
        # No frontmatter at all - insert a frontmatter block
        new_lines = ["---", "related:", new_entry, "---", *new_lines]

    new_content = source_newline.join(new_lines)
    _atomic_write_restore(path, new_content)
    return True


def _extract_stem(wiki_link: str) -> str | None:
    """Return the bare stem from a ``[[stem]]`` or bare-stem string.

    Args:
        wiki_link: Input string; may be ``[[stem]]``, ``'[[stem]]'``,
            or just ``stem``.

    Returns:
        The bare stem, or ``None`` if the string is empty.
    """
    s = wiki_link.strip().strip("'\"")
    if s.startswith("[[") and s.endswith("]]"):
        inner = s[2:-2]
        if "|" in inner:
            inner = inner.split("|", 1)[0]
        return inner.strip() or None
    return s or None
