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

import datetime as _dt
import re
from typing import TYPE_CHECKING

import yaml

from ..core.helpers import atomic_write
from .models import refresh_modified_stamp

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
    # Vault-orientation ADR (decision D3): a link mutation refreshes the
    # target document's modified stamp.
    new_content = refresh_modified_stamp(new_content, _dt.date.today())
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

    When the existing ``related:`` value is a non-empty inline (flow)
    sequence, the whole key is first normalised to block form so the
    append cannot corrupt the YAML; if that value cannot be safely parsed
    a :class:`ValueError` is raised rather than writing unparseable bytes.

    Returns:
        ``True`` when the entry was appended; ``False`` when the entry
        already existed (idempotent no-op).

    Raises:
        OSError: When the file cannot be read or written.
        UnicodeDecodeError: When the content is not valid UTF-8.
        ValueError: When *wiki_link* cannot be parsed to a stem, or when an
            existing inline ``related:`` value cannot be safely normalised.
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
    inline_value: str | None = None

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
                # Capture any inline value: `related: []` (empty) or
                # `related: ['[[a]]']` (a flow sequence requiring normalisation).
                stripped = line[len("related:") :].strip()
                inline_value = stripped if stripped not in ("", "[]") else None
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

    new_entry = f"  - '[[{stem}]]'"

    new_lines = list(lines)

    if related_idx is not None and inline_value is not None:
        # Non-empty inline/flow sequence (e.g. `related: ['[[a]]']`).  Block
        # surgery cannot append a list item beneath a flow key without
        # producing unparseable YAML, so normalise the whole key to block
        # form first, then append.  The ADR forbids writing corrupt YAML, so
        # any value that cannot be parsed into a flow sequence raises.
        existing_stems = _parse_inline_related(inline_value)
        # Idempotency: the new stem may already be in the inline sequence.
        if any(s.lower() == stem.lower() for s in existing_stems):
            return False
        block_lines = [f"  - '[[{_normalise_stem(s)}]]'" for s in existing_stems]
        block_lines.append(new_entry)
        new_lines[related_idx] = "related:"
        new_lines[related_idx + 1 : related_idx + 1] = block_lines
    elif related_idx is not None and last_related_item_idx is not None:
        # Populated block list: append after the last existing item so the
        # new entry lands at the END of the list (the docstring contract).
        new_lines.insert(last_related_item_idx + 1, new_entry)
    elif related_idx is not None:
        # Genuinely empty list: `related:` (bare) or `related: []` with no
        # block items.  Rewrite the key to block form and seed the entry.
        new_lines[related_idx] = "related:"
        new_lines.insert(related_idx + 1, new_entry)
    elif frontmatter_close_idx is not None:
        # No related: key found - insert one before the closing ---
        new_lines.insert(frontmatter_close_idx, new_entry)
        new_lines.insert(frontmatter_close_idx, "related:")
    else:
        # No frontmatter at all - insert a frontmatter block
        new_lines = ["---", "related:", new_entry, "---", *new_lines]

    new_content = source_newline.join(new_lines)
    # Vault-orientation ADR (decision D3): a link mutation refreshes the
    # target document's modified stamp.
    new_content = refresh_modified_stamp(new_content, _dt.date.today())
    _atomic_write_restore(path, new_content)
    return True


def _parse_inline_related(inline_value: str) -> list[str]:
    """Parse the inline value of a ``related:`` key into bare stems.

    Used when ``related:`` holds a YAML flow sequence such as
    ``['[[a]]', '[[b]]']`` that must be normalised to block form before a
    new entry is appended.  Each parsed item is reduced to its bare stem so
    the rewritten block can re-quote consistently.

    Args:
        inline_value: The text after ``related:`` on the key line, already
            stripped of surrounding whitespace (e.g. ``"['[[a]]']"``).

    Returns:
        The bare stems of every entry in the flow sequence, in order.

    Raises:
        ValueError: When *inline_value* is not a parseable YAML flow
            sequence of strings, or any item is not a wiki-link.  Raising
            here forces the caller to surface a ``failed`` envelope rather
            than write corrupt YAML.
    """
    try:
        parsed = yaml.safe_load(f"related: {inline_value}")
    except yaml.YAMLError as exc:
        raise ValueError(
            f"Cannot parse inline related: value {inline_value!r}: {exc}"
        ) from exc

    value = parsed.get("related") if isinstance(parsed, dict) else None
    if not isinstance(value, list):
        raise ValueError(f"Inline related: value is not a sequence: {inline_value!r}")

    stems: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"Inline related: entry is not a string: {item!r}")
        stem = _extract_stem(item)
        if not stem:
            raise ValueError(f"Inline related: entry has no stem: {item!r}")
        stems.append(stem)
    return stems


def _normalise_stem(stem: str) -> str:
    """Return *stem* unwrapped of any residual ``[[ ]]`` or quoting.

    Args:
        stem: A bare stem or a ``[[stem]]`` form.

    Returns:
        The bare stem suitable for re-wrapping as ``'[[stem]]'``.
    """
    extracted = _extract_stem(stem)
    return extracted if extracted is not None else stem


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
