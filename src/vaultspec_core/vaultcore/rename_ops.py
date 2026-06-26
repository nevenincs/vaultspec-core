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

__all__ = ["rename_document_path", "rewrite_incoming_refs"]

logger = logging.getLogger(__name__)


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
            exact_names = {path.name for path in src.parent.iterdir()}
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


def rewrite_incoming_refs(
    root_dir: Path,
    renames: list[tuple[str, str]],
    result: CheckResult,
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
    """
    from .checks._base import CheckDiagnostic, Severity

    if not renames:
        return

    raw_map = {old: new for old, new in renames if old != new}
    if not raw_map:
        return

    # Collapse rename chains so [[A]] -> [[C]] when ``A -> B`` and ``B -> C``
    # both happened in the same check run.  Cycles of any length
    # (``A -> B -> A``, ``A -> B -> C -> A``, ...) are detected by
    # tracking the set of visited nodes during the traversal: as soon as
    # we encounter a node we have already seen, the chain is a cycle and
    # the entry is dropped from the rewrite map rather than emitted as a
    # false rewrite.
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
    # by the dot-prefix filter below.
    non_schema_dirs = frozenset({"data", "logs"})

    for md_path in sorted(vault_root.rglob("*.md")):
        # Skip hidden internal directories (e.g. ``.obsidian/``,
        # ``.trash/``, ``.vaultspec``-style dotfile scratch) and
        # non-schema data/log directories.  These are covered by the
        # managed gitignore block and must not be mutated - Obsidian
        # in particular keeps its own state files under ``.obsidian/``
        # that should never be edited externally.
        try:
            rel_parts = md_path.relative_to(vault_root).parts
        except ValueError:
            continue
        if any(
            part.startswith(".") or part in non_schema_dirs for part in rel_parts[:-1]
        ):
            continue
        try:
            # Read as bytes first so CRLF endings survive the decode;
            # ``read_text`` collapses them via universal newlines.
            raw = md_path.read_bytes()
            content = raw.decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            logger.warning("Failed to read %s for ref rewrite: %s", md_path, exc)
            continue

        # Preserve a UTF-8 BOM if present; the scanner strips it so the
        # opening ``---`` fence matches but the write-back restores it.
        # Use the ``\ufeff`` escape rather than the literal character so
        # the source is legible in editors that hide zero-width glyphs.
        bom = ""
        if content.startswith("\ufeff"):
            bom = "\ufeff"
            content = content[1:]

        # Preserve the file's line-ending convention across the rewrite
        # so we do not ship mixed CRLF/LF endings back to disk.
        newline = "\r\n" if "\r\n" in content else "\n"
        lines = content.splitlines()
        in_frontmatter = False
        in_related = False
        changed = False
        fence_closed = False
        budget_exceeded = False
        # Tracks wiki-link targets already present in the ``related:``
        # block so we can drop duplicate lines that the rewrite would
        # otherwise introduce (e.g. when two sources collapse onto the
        # same terminal or when the terminal already appeared in the
        # list).  Anchored/aliased forms are normalised to their stem
        # component for dedup purposes.
        seen_targets: set[str] = set()
        drop_idx: list[int] = []

        for idx, line in enumerate(lines):
            # Guard against a missing closing fence: if the file is not
            # a real vault document, bail out of the scan after a fixed
            # line budget rather than scanning prose forever.
            if in_frontmatter and idx > _FRONTMATTER_LINE_BUDGET:
                budget_exceeded = True
                break

            stripped = line.strip()
            if stripped == "---":
                if not in_frontmatter:
                    in_frontmatter = True
                else:
                    fence_closed = True
                    break
                continue

            if not in_frontmatter:
                continue

            if line.strip().startswith("related:"):
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
            # Extract the bare stem from Obsidian link forms:
            # ``stem``, ``stem#heading``, ``stem|alias``, or
            # ``stem#heading|alias``.  Rename matching is always on
            # the stem alone; the anchor and alias are preserved on
            # the rewritten line.
            stem_only = target
            trailer = ""
            anchor_hash = stem_only.find("#")
            alias_pipe = stem_only.find("|")
            cut_candidates = [i for i in (anchor_hash, alias_pipe) if i >= 0]
            if cut_candidates:
                cut = min(cut_candidates)
                stem_only = target[:cut]
                trailer = target[cut:]

            # Case-sensitive lookup first (preserves exact-case intent
            # when both ``My-Doc.md`` and ``my-doc.md`` legitimately
            # coexist on Linux); fall back to case-insensitive match
            # so Obsidian-style cross-case links (``[[My-Doc]]`` at
            # pointing ``my-doc.md``) are still rewritten.
            final_stem: str | None = None
            if stem_only in rename_map:
                final_stem = rename_map[stem_only]
            elif stem_only.lower() in rename_map_lower:
                final_stem = rename_map_lower[stem_only.lower()]
            if final_stem is None:
                # Remember the existing (unrewritten) full target so
                # later rewrites can avoid creating a duplicate.  The
                # full target - not just the stem - is used because
                # ``[[beta]]`` and ``[[beta#heading]]`` are distinct
                # wiki-links that should both survive side by side.
                seen_targets.add(target)
                continue

            new_target = f"{final_stem}{trailer}"
            # If the exact post-rewrite target is already represented
            # by an earlier line in this related: block, drop this
            # line to avoid emitting a duplicate entry.
            if new_target in seen_targets:
                drop_idx.append(idx)
                changed = True
                try:
                    rel = md_path.relative_to(root_dir)
                except ValueError:
                    rel = md_path
                result.diagnostics.append(
                    CheckDiagnostic(
                        path=rel,
                        message=(
                            f"Dropped duplicate wiki-link: [[{target}]] "
                            f"-> [[{new_target}]] already present"
                        ),
                        severity=Severity.INFO,
                    )
                )
                continue

            lines[idx] = f"{match.group(1)}{new_target}{match.group(3)}"
            seen_targets.add(new_target)
            changed = True
            result.fixed_count += 1
            try:
                rel = md_path.relative_to(root_dir)
            except ValueError:
                rel = md_path
            result.diagnostics.append(
                CheckDiagnostic(
                    path=rel,
                    message=f"Updated wiki-link: [[{target}]] -> [[{new_target}]]",
                    severity=Severity.INFO,
                )
            )

        # Surface a warning diagnostic when the frontmatter exceeds the
        # line budget so operators can investigate documents whose
        # frontmatter may have been skipped mid-scan.
        if budget_exceeded:
            try:
                rel_path = md_path.relative_to(root_dir)
            except ValueError:
                rel_path = md_path
            result.diagnostics.append(
                CheckDiagnostic(
                    path=rel_path,
                    message=(
                        "Frontmatter exceeds "
                        f"{_FRONTMATTER_LINE_BUDGET} lines; "
                        "ref rewrite stopped at budget"
                    ),
                    severity=Severity.WARNING,
                )
            )

        if not changed:
            continue

        # Drop duplicate-collapsed lines in descending order so the
        # surviving indices stay stable while we mutate the list.
        for del_idx in sorted(drop_idx, reverse=True):
            del lines[del_idx]

        # If the scan never saw a closing fence we are in unknown
        # territory; skip writing rather than risk corrupting a file
        # whose frontmatter layout we misread.
        if in_frontmatter and not fence_closed:
            logger.warning(
                "Skipping rewrite of %s: closing frontmatter fence not found",
                md_path,
            )
            continue

        new_content = bom + newline.join(lines)
        # Preserve a trailing newline convention: if the original ended
        # with the detected newline, keep it.
        if content.endswith(newline):
            new_content += newline
        try:
            atomic_write(md_path, new_content)
        except OSError as exc:
            logger.warning("Failed to rewrite %s: %s", md_path, exc)
