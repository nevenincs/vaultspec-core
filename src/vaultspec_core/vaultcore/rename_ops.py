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
from .parser import FrontmatterSplit, related_block, split_frontmatter

if TYPE_CHECKING:
    from pathlib import Path

    from .checks._base import CheckResult

__all__ = [
    "count_related_rewrites",
    "find_rewrite_targets",
    "rename_document_path",
    "rewrite_incoming_refs",
    "split_keepends",
]

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


_MARKDOWN_SUFFIX = ".md"


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

    A ``.md`` suffix is dropped from the stem rather than carried in the
    trailer.  ``[[stem.md]]`` names the same document as ``[[stem]]`` and a
    rename map is keyed by bare stems, so keeping the suffix made a renamed
    document's incoming links unmatchable - the link then survived the
    rename pointing at a name no longer on disk, and the dangling check
    deleted it.  The rewritten link is written in the extension-less form
    the links check enforces anyway.
    """
    anchor_hash = target.find("#")
    alias_pipe = target.find("|")
    cut_candidates = [i for i in (anchor_hash, alias_pipe) if i >= 0]
    if not cut_candidates:
        stem, trailer = target, ""
    else:
        cut = min(cut_candidates)
        stem, trailer = target[:cut], target[cut:]
    if stem.lower().endswith(_MARKDOWN_SUFFIX):
        stem = stem[: -len(_MARKDOWN_SUFFIX)]
    return stem, trailer


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
) -> tuple[list[tuple[bool, str, str]], list[int]]:
    """Rewrite matching ``related:`` entries in *pairs* in place.

    Args:
        pairs: ``[content, ending]`` pairs of the frontmatter's YAML lines;
            the content of rewritten lines is mutated in place.
        rename_map: Exact-case ``old_stem`` -> terminal ``new_stem`` map.
        rename_map_lower: Lowercased mirror of *rename_map*.

    Returns:
        A ``(events, drop_idx)`` tuple where ``events`` holds
        ``(dropped, target, new_target)`` triples in line order and
        ``drop_idx`` holds the indices of duplicate lines to delete.
    """
    # Tracks wiki-link targets already present in the ``related:`` block so
    # duplicate lines the rewrite would otherwise introduce can be dropped
    # (e.g. when two sources collapse onto the same terminal or when the
    # terminal already appeared in the list).
    seen_targets: set[str] = set()
    drop_idx: list[int] = []
    events: list[tuple[bool, str, str]] = []

    for entry in related_block([pair[0] for pair in pairs]).entries:
        target = entry.target
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
            drop_idx.append(entry.index)
            events.append((True, target, new_target))
            continue

        pairs[entry.index][0] = f"{entry.prefix}{new_target}{entry.suffix}"
        seen_targets.add(new_target)
        events.append((False, target, new_target))

    return events, drop_idx


def _scan_document(
    content: str, rename_map: dict[str, str], rename_map_lower: dict[str, str]
) -> tuple[FrontmatterSplit, list[list[str]], list[tuple[bool, str, str]], list[int]]:
    """Scan *content*'s ``related:`` list for the rewrites a rename set makes.

    The single scan behind the rewrite, its lock-target preview, and the
    dry-run count, so the three agree on every document.

    Args:
        content: The full document text.
        rename_map: Exact-case ``old_stem`` -> terminal ``new_stem`` map.
        rename_map_lower: Lowercased mirror of *rename_map*.

    Returns:
        ``(split, pairs, events, drop_idx)``: the frontmatter split, the
        YAML lines as ``[content, ending]`` pairs with rewritten entries
        applied, and :func:`_scan_related_block`'s events and drop indices.
        A document with no frontmatter yields no pairs and no events.
    """
    split = split_frontmatter(content)
    if split.yaml_block is None:
        return split, [], [], []
    # Model each YAML line as a mutable ``[content, ending]`` pair so the
    # rewrite touches only the content of the lines it targets and every other
    # byte - a byte-order mark, exotic in-line separators, and a CR-only or
    # absent trailing terminator - survives verbatim.
    pairs = split_keepends(content[split.yaml_start : split.yaml_end])
    events, drop_idx = _scan_related_block(pairs, rename_map, rename_map_lower)
    return split, pairs, events, drop_idx


def _rename_maps(
    renames: list[tuple[str, str]],
) -> tuple[dict[str, str], dict[str, str]]:
    """Return the collapsed rename map for *renames* and its lowercased mirror.

    The mirror serves case-insensitive fallback lookups: Obsidian resolves
    wiki-links case-insensitively (``[[My-Doc]]`` hits ``my-doc.md``) while a
    Linux filesystem is case-sensitive, so the exact-case lookup is tried
    first to preserve intent.
    """
    raw_map = {old: new for old, new in renames if old != new}
    rename_map = _collapse_rename_chains(raw_map) if raw_map else {}
    return rename_map, {k.lower(): v for k, v in rename_map.items()}


def count_related_rewrites(
    root_dir: Path,
    renames: list[tuple[str, str]],
    *,
    exclude_dirs: frozenset[str] = frozenset(),
    removed: frozenset[Path] = frozenset(),
) -> int:
    """Return how many ``related:`` entries a rename would rewrite.

    Counts exactly what :func:`rewrite_incoming_refs` rewrites for the same
    arguments: the same documents, rename map and scan, with entries dropped
    as duplicates left out, so a dry run reports what the rename then does.

    Args:
        root_dir: Project root (the caller's workspace).
        renames: ``(old_stem, new_stem)`` pairs.
        exclude_dirs: Further top-level ``<docs_dir>`` subdirectories to
            skip, as :func:`rewrite_incoming_refs` takes them.
        removed: Documents the rename deletes before its rewrite runs, whose
            links are therefore never rewritten.

    Returns:
        The number of entries that would be rewritten.
    """
    rename_map, rename_map_lower = _rename_maps(renames)
    if not rename_map:
        return 0
    total = 0
    for path in _rewrite_candidates(root_dir, exclude_dirs):
        if path in removed:
            continue
        content = _read_document_text(path)
        if content is None:
            continue
        _split, _pairs, events, _drop = _scan_document(
            content, rename_map, rename_map_lower
        )
        total += sum(1 for dropped, _target, _new in events if not dropped)
    return total


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

    try:
        rel = md_path.relative_to(root_dir)
    except ValueError:
        rel = md_path

    split, pairs, events, drop_idx = _scan_document(
        content, rename_map, rename_map_lower
    )
    if split.unclosed:
        # Frontmatter whose fence never closes has no known extent: rewriting
        # it could corrupt body lines. Surface it only when it links a renamed
        # document, so an unrelated malformed file stays quiet.
        lowered = content.lower()
        if any(f"[[{old}" in lowered for old in rename_map_lower):
            result.diagnostics.append(
                CheckDiagnostic(
                    path=rel,
                    message=(
                        "Frontmatter fence never closes; related links were "
                        "not rewritten"
                    ),
                    severity=Severity.WARNING,
                )
            )
        return

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

    if not events:
        return

    # Drop duplicate-collapsed lines in descending order so the surviving
    # indices stay stable while we mutate the list. Deleting the whole
    # ``[content, ending]`` pair removes the line's terminator with it, so no
    # stray blank line or doubled terminator is left behind.
    for del_idx in sorted(drop_idx, reverse=True):
        del pairs[del_idx]

    new_content = (
        content[: split.yaml_start]
        + "".join(c + e for c, e in pairs)
        + content[split.yaml_end :]
    )
    try:
        atomic_write(md_path, new_content)
    except OSError as exc:
        logger.warning("Failed to rewrite %s: %s", md_path, exc)


def find_rewrite_targets(
    root_dir: Path,
    renames: list[tuple[str, str]],
    *,
    exclude_dirs: frozenset[str] = frozenset(),
) -> list[Path]:
    """Return every document :func:`rewrite_incoming_refs` would actually WRITE.

    A read-only mirror of :func:`rewrite_incoming_refs`'s own scan - same skip
    rules (:func:`_is_skipped_document`), same block-scoped match logic
    (:func:`_scan_related_block`) - used to determine the exact MUTATED set
    for a rename set before any mutation happens. A caller drives a rename
    through a domain-wide lock (see
    :class:`~vaultspec_core.vaultcore.rename_engine.RenameTransaction`) but
    that lock alone does not exclude an unrelated ``execute_edit`` call on one
    of the referrer documents the cascade is about to rewrite; taking a
    per-document lock for exactly this set closes that gap without locking
    the whole docs tree (which every OTHER document the cascade merely reads
    and finds no match in does not need to be excluded from).

    Because it shares the identical matching logic, the set this returns is
    exactly the set :func:`rewrite_incoming_refs` would write for the same
    *renames* against the same on-disk state; it stays accurate between the
    two calls only because the caller holds the docs-domain lock across both
    (see :class:`~vaultspec_core.vaultcore.rename_engine.RenameTransaction`).
    A document that starts referencing the renamed stem only after this scan
    (a concurrent ``execute_edit`` adding a ``related:`` entry, landing in the
    window between this scan and the cascade) is not in the returned set and
    so is not locked; that residual is bounded and named at the call site
    that decides how to use this function, not swallowed here.

    Args:
        root_dir: Project root (the caller's workspace).
        renames: ``(old_stem, new_stem)`` pairs, exactly as passed to
            :func:`rewrite_incoming_refs`.
        exclude_dirs: Additional top-level docs subdirectories to skip,
            mirroring :func:`rewrite_incoming_refs`'s parameter of the same
            name.

    Returns:
        Absolute paths of every document whose ``related:`` block contains a
        wiki-link this rename set would rewrite, sorted for a deterministic
        lock-acquisition order. Never includes the renamed document itself -
        a rename is not a self-referencing rewrite - so a caller that also
        needs the renamed document locked adds it separately.
    """
    rename_map, rename_map_lower = _rename_maps(renames)
    if not rename_map:
        return []

    targets: list[Path] = []
    for md_path in _rewrite_candidates(root_dir, exclude_dirs):
        content = _read_document_text(md_path)
        if content is None:
            continue
        _split, _pairs, events, _drop = _scan_document(
            content, rename_map, rename_map_lower
        )
        if events:
            targets.append(md_path)
    return targets


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

    rename_map, rename_map_lower = _rename_maps(renames)
    if not rename_map:
        return

    for md_path in _rewrite_candidates(root_dir, exclude_dirs):
        _rewrite_document_refs(md_path, root_dir, rename_map, rename_map_lower, result)


def _rewrite_candidates(root_dir: Path, exclude_dirs: frozenset[str]) -> list[Path]:
    """Return the documents a ``related:`` rewrite reads, in sorted order.

    Top-level vault subdirectories are expected to hold schema-conforming
    documents. Non-schema directories such as ``data/`` and ``logs/``
    (recommended for gitignore by
    :func:`vaultspec_core.core.gitignore.get_recommended_entries`) are skipped
    to avoid scanning large or non-vault files, and hidden directories
    (``.obsidian/``, ``.trash/``, ...) by the dot-prefix filter in
    :func:`_is_skipped_document`.

    Args:
        root_dir: Project root (the caller's workspace).
        exclude_dirs: Further top-level ``<docs_dir>`` subdirectories to skip.

    Returns:
        The candidate paths; empty when the docs directory does not exist.
    """
    from ..config import get_config

    vault_root = root_dir / get_config().docs_dir
    if not vault_root.is_dir():
        return []
    non_schema_dirs = frozenset({"data", "logs"}) | exclude_dirs
    return [
        md_path
        for md_path in sorted(vault_root.rglob("*.md"))
        if not _is_skipped_document(md_path, vault_root, non_schema_dirs)
    ]
