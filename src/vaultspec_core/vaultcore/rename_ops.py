"""Shared rename primitives for vault documents.

Two hardened primitives live here so the structure check and the
feature-rename backend call one implementation rather than maintaining
parallel copies:

- :func:`rename_document_path` renames a file on disk, handling
  case-only renames on case-insensitive filesystems via a temporary
  same-directory two-hop.
- :func:`rewrite_incoming_refs` rewrites ``[[old_stem]]`` ->
  ``[[new_stem]]`` wiki-links across the whole docs tree, scoped strictly
  to the ``related:`` frontmatter block, collapsing rename chains,
  dropping cycles, deduping colliding targets, and preserving CRLF
  endings and a UTF-8 BOM byte-for-byte.

The module deliberately carries no module-level dependency on
:mod:`vaultspec_core.vaultcore.checks`; the diagnostic types consumed by
:func:`rewrite_incoming_refs` are imported lazily inside the function so
importing this module never triggers the checks package (which imports
back from here), keeping the shared module free of an import cycle.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING
from uuid import uuid4

from ..core.helpers import atomic_write

if TYPE_CHECKING:
    from pathlib import Path

    from .checks._base import CheckResult

__all__ = ["rename_document_path", "rewrite_incoming_refs", "split_keepends"]

logger = logging.getLogger(__name__)


# Split only on the three canonical hard line breaks - LF, CRLF, and the
# classic-Mac bare CR - and NEVER on the exotic Unicode line separators that
# ``str.splitlines`` also treats as breaks (form feed U+000C, vertical tab
# U+000B, NEL U+0085, LS U+2028, PS U+2029). Those exotic characters occur
# inside body prose and must survive a rename byte-for-byte; treating them as
# line breaks is exactly the corruption this module exists to prevent.
_LINE_SPLIT_RE = re.compile(r"(\r\n|\r|\n)")


def split_keepends(text: str) -> list[list[str]]:
    r"""Split *text* into mutable ``[content, ending]`` pairs.

    Breaks only on ``\r\n`` / ``\r`` / ``\n`` (never the exotic Unicode line
    separators), so ``"".join(c + e for c, e in pairs)`` reproduces *text*
    byte-for-byte. Editing only specific ``content`` values while keeping each
    ``ending`` intact therefore cannot normalize endings or fabricate line
    breaks out of in-line form feeds, vertical tabs, NEL, LS, or PS.

    Examples:
        ``"a\nb\n"`` -> ``[["a", "\n"], ["b", "\n"]]``;
        ``"a\nb"`` -> ``[["a", "\n"], ["b", ""]]``;
        ``""`` -> ``[]``;
        ``"\n"`` -> ``[["", "\n"]]``.

    Args:
        text: The text to split.

    Returns:
        A list of ``[content, ending]`` pairs where ``ending`` is the exact
        terminator that followed ``content`` (``""`` for a final unterminated
        line).
    """
    if not text:
        return []
    # ``parts`` is ``[c0, sep0, c1, sep1, ..., cLast]`` because the regex group
    # captures the separator: every odd index is a terminator, every even index
    # is the content that preceded it.
    parts = _LINE_SPLIT_RE.split(text)
    pairs: list[list[str]] = [
        [parts[i], parts[i + 1]] for i in range(0, len(parts) - 1, 2)
    ]
    # ``parts[-1]`` is the trailing content after the final terminator; append
    # it with an empty ending only when the text did not end on a break.
    if parts[-1]:
        pairs.append([parts[-1], ""])
    return pairs


def _paths_refer_to_same_file(src: Path, dst: Path) -> bool:
    """Return True when *src* and *dst* identify the same on-disk file."""
    try:
        return src.samefile(dst)
    except OSError:
        return False


def _case_rename_temp_path(src: Path) -> Path:
    """Return a short same-directory temp path for a case-only rename hop."""
    return src.with_name(f".vs-{uuid4().hex[:12]}.tmp")


def _absolute_path_text(path: Path) -> str:
    """Return an absolute path string without requiring the path to exist."""
    try:
        return str(path.resolve(strict=False))
    except OSError:
        return str(path.absolute())


def rename_document_path(src: Path, dst: Path) -> bool:
    """Rename *src* to *dst*, including case-only renames on Windows.

    Case-insensitive filesystems can report that a desired destination
    exists even when it is just the source file under different casing.
    In that situation, force the casing update through a temporary
    same-directory hop so the final name is materialized on disk.
    """
    if str(src) == str(dst):
        return False

    if src.name.lower() == dst.name.lower() and src.name != dst.name:
        try:
            exact_names: set[str] = {path.name for path in src.parent.iterdir()}
        except OSError:
            exact_names = set()
        if dst.name in exact_names:
            return src.name not in exact_names
        for _attempt in range(10):
            tmp = _case_rename_temp_path(src)
            if tmp.exists():
                continue
            try:
                src.rename(tmp)
            except OSError:
                return False
            try:
                tmp.rename(dst)
                return True
            except OSError:
                try:
                    tmp.rename(src)
                except OSError:
                    logger.warning(
                        "Failed to roll back case-only rename temp path; "
                        "manual recovery may be needed. temp=%s source=%s "
                        "destination=%s",
                        _absolute_path_text(tmp),
                        _absolute_path_text(src),
                        _absolute_path_text(dst),
                    )
                return False
        return False

    if dst.exists() and not _paths_refer_to_same_file(src, dst):
        return False

    src.rename(dst)
    return True


_RELATED_ENTRY_RE = re.compile(r'^(\s*-\s*["\']?\[\[)(.+?)(\]\]["\']?.*)$')
_FRONTMATTER_LINE_BUDGET = 200


def _collapse_rename_chains(raw_map: dict[str, str]) -> dict[str, str]:
    """Resolve each rename to its terminal target, dropping cyclic chains.

    Collapses ``[[A]]`` -> ``[[C]]`` when ``A -> B`` and ``B -> C`` both
    happened in the same check run.  Cycles of any length (``A -> B -> A``,
    ``A -> B -> C -> A``, ...) are detected by tracking the set of visited
    nodes during the traversal: as soon as a node is encountered twice the
    chain is a cycle and the entry is dropped from the rewrite map rather
    than emitted as a false rewrite.
    """
    rename_map: dict[str, str] = {}
    for old in raw_map:
        visited: set[str] = {old}
        current = raw_map[old]
        cycle = False
        while current in raw_map:
            if current in visited:
                cycle = True
                break
            visited.add(current)
            current = raw_map[current]
        if not cycle:
            rename_map[old] = current
    return rename_map


def _is_skipped_document(
    md_path: Path, vault_root: Path, non_schema_dirs: frozenset[str]
) -> bool:
    """Return True when *md_path* must not be rewritten.

    Skips hidden internal directories (e.g. ``.obsidian/``, ``.trash/``,
    ``.vaultspec``-style dotfile scratch) and non-schema data/log
    directories.  These are covered by the managed gitignore block and must
    not be mutated - Obsidian in particular keeps its own state files under
    ``.obsidian/`` that should never be edited externally.  Symlinked
    ``*.md`` files are skipped too: a symlinked document is not a legitimate
    vault file, and reading/writing it would touch an out-of-bounds target
    (or pull its bytes into the vault).
    """
    try:
        rel_parts = md_path.relative_to(vault_root).parts
    except ValueError:
        return True
    if any(part.startswith(".") or part in non_schema_dirs for part in rel_parts[:-1]):
        return True
    return md_path.is_symlink()


def _read_document_text(md_path: Path) -> str | None:
    """Return the decoded text of *md_path*, or None when it cannot be read."""
    try:
        # Read as bytes first so CRLF endings survive the decode;
        # ``read_text`` collapses them via universal newlines.
        return md_path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning("Failed to read %s for ref rewrite: %s", md_path, exc)
        return None


def _split_link_target(target: str) -> tuple[str, str]:
    """Split a wiki-link target into its bare stem and its trailer.

    Handles the Obsidian link forms ``stem``, ``stem#heading``,
    ``stem|alias``, and ``stem#heading|alias``.  Rename matching is always
    on the stem alone; the anchor and alias travel in the trailer so they
    are preserved on the rewritten line.
    """
    anchor_hash = target.find("#")
    alias_pipe = target.find("|")
    cut_candidates = [i for i in (anchor_hash, alias_pipe) if i >= 0]
    if not cut_candidates:
        return target, ""
    cut = min(cut_candidates)
    return target[:cut], target[cut:]


def _resolve_renamed_stem(
    stem: str, rename_map: dict[str, str], rename_map_lower: dict[str, str]
) -> str | None:
    """Return the terminal stem for *stem*, or None when it was not renamed.

    Case-sensitive lookup first (preserves exact-case intent when both
    ``My-Doc.md`` and ``my-doc.md`` legitimately coexist on Linux); falls
    back to a case-insensitive match so Obsidian-style cross-case links
    (``[[My-Doc]]`` pointing at ``my-doc.md``) are still rewritten.
    """
    if stem in rename_map:
        return rename_map[stem]
    return rename_map_lower.get(stem.lower())


def _scan_related_block(
    pairs: list[list[str]],
    rename_map: dict[str, str],
    rename_map_lower: dict[str, str],
) -> tuple[list[tuple[bool, str, str]], list[int], bool, bool]:
    """Rewrite matching ``related:`` entries in *pairs* in place.

    Args:
        pairs: ``[content, ending]`` line pairs for the whole document; the
            content of rewritten lines is mutated in place.
        rename_map: Exact-case ``old_stem`` -> terminal ``new_stem`` map.
        rename_map_lower: Lowercased mirror of *rename_map*.

    Returns:
        A ``(events, drop_idx, budget_exceeded, fence_missing)`` tuple where
        ``events`` holds ``(dropped, target, new_target)`` triples in line
        order, ``drop_idx`` holds the indices of duplicate lines to delete,
        and ``fence_missing`` is True when a frontmatter block opened but
        never closed.
    """
    in_frontmatter = False
    in_related = False
    fence_closed = False
    budget_exceeded = False
    # Tracks wiki-link targets already present in the ``related:`` block so
    # duplicate lines the rewrite would otherwise introduce can be dropped
    # (e.g. when two sources collapse onto the same terminal or when the
    # terminal already appeared in the list).
    seen_targets: set[str] = set()
    drop_idx: list[int] = []
    events: list[tuple[bool, str, str]] = []

    for idx, pair in enumerate(pairs):
        # Guard against a missing closing fence: if the file is not a real
        # vault document, bail out of the scan after a fixed line budget
        # rather than scanning prose forever. ``idx`` indexes logical lines
        # (the pairs), matching the pre-pair behaviour.
        if in_frontmatter and idx > _FRONTMATTER_LINE_BUDGET:
            budget_exceeded = True
            break

        line = pair[0]
        stripped = line.strip()
        if stripped == "---":
            if in_frontmatter:
                fence_closed = True
                break
            in_frontmatter = True
            continue

        if not in_frontmatter:
            continue

        if stripped.startswith("related:"):
            in_related = True
            continue

        if in_related and line and not line.startswith((" ", "\t", "-")):
            in_related = False

        if not in_related:
            continue

        match = _RELATED_ENTRY_RE.match(line)
        if not match:
            continue

        target = match.group(2)
        stem_only, trailer = _split_link_target(target)
        final_stem = _resolve_renamed_stem(stem_only, rename_map, rename_map_lower)
        if final_stem is None:
            # Remember the existing (unrewritten) full target so later
            # rewrites can avoid creating a duplicate.  The full target -
            # not just the stem - is used because ``[[beta]]`` and
            # ``[[beta#heading]]`` are distinct wiki-links that should both
            # survive side by side.
            seen_targets.add(target)
            continue

        new_target = f"{final_stem}{trailer}"
        # If the exact post-rewrite target is already represented by an
        # earlier line in this related: block, drop this line to avoid
        # emitting a duplicate entry.
        if new_target in seen_targets:
            drop_idx.append(idx)
            events.append((True, target, new_target))
            continue

        pair[0] = f"{match.group(1)}{new_target}{match.group(3)}"
        seen_targets.add(new_target)
        events.append((False, target, new_target))

    return events, drop_idx, budget_exceeded, in_frontmatter and not fence_closed


def _rewrite_document_refs(
    md_path: Path,
    root_dir: Path,
    rename_map: dict[str, str],
    rename_map_lower: dict[str, str],
    result: CheckResult,
) -> None:
    """Rewrite the ``related:`` block of a single document and write it back."""
    from .checks._base import CheckDiagnostic, Severity

    content = _read_document_text(md_path)
    if content is None:
        return

    # Preserve a UTF-8 BOM if present; the scanner strips it so the opening
    # ``---`` fence matches but the write-back restores it.  Use the
    # ``﻿`` escape rather than the literal character so the source is
    # legible in editors that hide zero-width glyphs.
    bom = ""
    if content.startswith("﻿"):
        bom = "﻿"
        content = content[1:]

    # Model each line as a mutable ``[content, ending]`` pair so the rewrite
    # touches only the content of the lines it targets and every other byte -
    # including exotic in-line separators and a CR-only or absent trailing
    # terminator - survives verbatim.
    pairs = split_keepends(content)
    events, drop_idx, budget_exceeded, fence_missing = _scan_related_block(
        pairs, rename_map, rename_map_lower
    )

    try:
        rel = md_path.relative_to(root_dir)
    except ValueError:
        rel = md_path

    for dropped, target, new_target in events:
        if dropped:
            message = (
                f"Dropped duplicate wiki-link: [[{target}]] "
                f"-> [[{new_target}]] already present"
            )
        else:
            result.fixed_count += 1
            message = f"Updated wiki-link: [[{target}]] -> [[{new_target}]]"
        result.diagnostics.append(
            CheckDiagnostic(path=rel, message=message, severity=Severity.INFO)
        )

    # Surface a warning diagnostic when the frontmatter exceeds the line
    # budget so operators can investigate documents whose frontmatter may
    # have been skipped mid-scan.
    if budget_exceeded:
        result.diagnostics.append(
            CheckDiagnostic(
                path=rel,
                message=(
                    "Frontmatter exceeds "
                    f"{_FRONTMATTER_LINE_BUDGET} lines; "
                    "ref rewrite stopped at budget"
                ),
                severity=Severity.WARNING,
            )
        )

    if not events:
        return

    # Drop duplicate-collapsed lines in descending order so the surviving
    # indices stay stable while we mutate the list. Deleting the whole
    # ``[content, ending]`` pair removes the line's terminator with it, so no
    # stray blank line or doubled terminator is left behind.
    for del_idx in sorted(drop_idx, reverse=True):
        del pairs[del_idx]

    # If the scan never saw a closing fence we are in unknown territory;
    # skip writing rather than risk corrupting a file whose frontmatter
    # layout we misread.
    if fence_missing:
        logger.warning(
            "Skipping rewrite of %s: closing frontmatter fence not found",
            md_path,
        )
        return

    # Reassemble from the pairs: each line carries its own original
    # terminator, so the trailing newline (or its absence) and every
    # mixed/CR-only ending are reproduced exactly. The BOM is re-prepended.
    new_content = bom + "".join(c + e for c, e in pairs)
    try:
        atomic_write(md_path, new_content)
    except OSError as exc:
        logger.warning("Failed to rewrite %s: %s", md_path, exc)


def rewrite_incoming_refs(
    root_dir: Path,
    renames: list[tuple[str, str]],
    result: CheckResult,
    *,
    exclude_dirs: frozenset[str] = frozenset(),
) -> None:
    """Rewrite ``[[old_stem]]`` -> ``[[new_stem]]`` in ``related:`` frontmatter.

    Walks every ``*.md`` file under the configured docs directory directly off
    the filesystem (the renames have already happened on disk; the
    in-memory :class:`VaultSnapshot` is now stale).  Inspects the YAML
    frontmatter ``related:`` list and rewrites any matching wiki-link
    entry.  Only operates on the ``related:`` block - body prose is left
    untouched so free-text mentions of the old filename do not
    accidentally mutate.

    The scanner recognises the block-sequence form
    (``- "[[stem]]"`` / ``- '[[stem]]'`` / ``- [[stem]]``) which is the
    form enforced by the vault template and used throughout this
    project.  YAML flow-style lists (``related: ["[[stem]]"]``) are not
    currently rewritten; ``vaultspec-core vault check frontmatter`` enforces block
    style.

    Each rewrite bumps :attr:`CheckResult.fixed_count` and appends an
    INFO diagnostic.  Read/write failures for individual documents log a
    warning and do not abort the pass.

    Args:
        root_dir: Project root (the caller's workspace).
        renames: List of ``(old_stem, new_stem)`` pairs produced by a
            caller such as
            :func:`~vaultspec_core.vaultcore.checks.structure._fix_filename`.
        result: :class:`CheckResult` to accumulate diagnostics and fix
            counts into.
        exclude_dirs: Top-level ``<docs_dir>`` subdirectory names to skip in
            addition to the always-skipped ``data``/``logs`` and dot-prefixed
            directories. The feature-rename backend passes ``{"_archive"}`` so a
            rename never mutates archived documents (which it also does not
            snapshot for rollback); the structure check passes nothing, keeping
            its whole-vault behaviour unchanged.
    """
    if not renames:
        return

    raw_map = {old: new for old, new in renames if old != new}
    if not raw_map:
        return

    rename_map = _collapse_rename_chains(raw_map)

    from ..config import get_config

    vault_root = root_dir / get_config().docs_dir
    if not vault_root.is_dir():
        return

    # Build a case-insensitive mirror of ``rename_map`` for fallback
    # lookups.  Obsidian resolves wiki-links case-insensitively
    # (``[[My-Doc]]`` hits ``my-doc.md``) but the filesystem on Linux
    # is case-sensitive.  We try the exact-case lookup first to
    # preserve intent and only fall back to lowercase when no exact
    # match exists.
    rename_map_lower = {k.lower(): v for k, v in rename_map.items()}

    # Top-level vault subdirectories that are expected to contain
    # schema-conforming documents.  Non-schema directories such as
    # ``data/`` and ``logs/`` (explicitly recommended for gitignore
    # by :func:`vaultspec_core.core.gitignore.get_recommended_entries`)
    # are skipped to avoid scanning large or non-vault files.  Hidden
    # directories (``.obsidian/``, ``.trash/``, ...) are skipped
    # by the dot-prefix filter in :func:`_is_skipped_document`.
    non_schema_dirs = frozenset({"data", "logs"}) | exclude_dirs

    for md_path in sorted(vault_root.rglob("*.md")):
        if _is_skipped_document(md_path, vault_root, non_schema_dirs):
            continue
        _rewrite_document_refs(md_path, root_dir, rename_map, rename_map_lower, result)
