"""Add a ``related:`` edge between two vault documents: the one core writer.

``vault link add`` and ADR cross-referencing both write edges, so both call
this module rather than each resolving, deduplicating, locking and dropping
the graph cache on its own.

- **Resolution.** Both ends resolve the way ``--related`` inputs resolve: a
  stem, a filename, a path or a ``[[wiki-link]]``. The source must be a real
  document; a target that is not is a dangling edge, refused unless forced.
- **One read-modify-write under the lock.** The write reads the source,
  appends the entry and writes it back while holding the document's advisory
  lock, the same lock every body and frontmatter editor takes, so a
  concurrent edit is never silently overwritten.
- **Idempotent.** An edge the source already declares, however it is aliased,
  is left alone and reported unchanged.
- **Cache.** A write drops the graph cache, so the next graph build sees it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from vaultspec_core.core.exceptions import VaultSpecError

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "LinkError",
    "LinkResult",
    "LinkStatus",
    "add_related_link",
    "link_document",
]


class LinkError(VaultSpecError):
    """An edge could not be added; the message says why, in user terms."""


class LinkStatus(StrEnum):
    """Whether an edge was written."""

    CREATED = "created"
    UNCHANGED = "unchanged"


@dataclass(frozen=True)
class LinkResult:
    """The outcome of adding one edge.

    Attributes:
        status: ``created`` when the edge was (or, on a dry run, would be)
            written; ``unchanged`` when the source already declares it.
        src: The source document's stem.
        dst: The target's stem.
        dry_run: Whether nothing was written.
    """

    status: LinkStatus
    src: str
    dst: str
    dry_run: bool = False


def _declares(path: Path, dst: str) -> bool:
    """Return whether the document at *path* already links *dst*."""
    from .parser import parse_vault_metadata

    metadata, _ = parse_vault_metadata(path.read_text(encoding="utf-8"))
    wanted = dst.lower()
    for link in metadata.related:
        stem = link.strip().removeprefix("[[").removesuffix("]]")
        if stem.split("|", 1)[0].split("#", 1)[0].strip().lower() == wanted:
            return True
    return False


def link_document(root: Path, path: Path, dst: str) -> bool:
    """Append ``[[dst]]`` to the ``related:`` of the document at *path*.

    Args:
        root: The workspace root, whose lock directory and graph cache apply.
        path: The source document.
        dst: The target stem.

    Returns:
        ``True`` when the edge was written; ``False`` when it already existed.

    Raises:
        OSError: When the document cannot be read or written.
        ValueError: When the existing ``related:`` value cannot be extended
            safely.
        AdvisoryLockTimeoutError: When another writer holds the document's
            lock past the lock timeout.
    """
    from .edit_engine import document_write_lock, invalidate_graph_cache
    from .related_surgery import append_related_entry

    with document_write_lock(path, root):
        added = append_related_entry(path, f"[[{dst}]]")
    if added:
        invalidate_graph_cache(root)
    return added


def _normalise_stem(raw: str) -> str:
    """Return a best-effort stem from a reference that resolved to no document."""
    from pathlib import PurePath

    text = raw.strip().strip("'\"")
    if text.startswith("[[") and text.endswith("]]"):
        text = text[2:-2].split("|")[0].strip()
    return PurePath(text.removesuffix(".md")).name.lower()


def add_related_link(
    root: Path,
    src: str,
    dst: str,
    *,
    dry_run: bool = False,
    force: bool = False,
) -> LinkResult:
    """Add a ``related:`` edge from *src* to *dst*.

    Args:
        root: The workspace root.
        src: The source document reference.
        dst: The target document reference.
        dry_run: Report what would happen without writing.
        force: Allow a target that resolves to no document.

    Returns:
        The outcome.

    Raises:
        LinkError: When the source does not resolve, the target does not
            resolve and *force* is not set, or the write fails.
    """
    from .resolve import document_index, resolve_reference

    index = document_index(root)
    src_stem = resolve_reference(src, root, index)
    if src_stem is None:
        raise LinkError(f"Cannot resolve source document: '{src}'")
    src_path = index[src_stem.lower()]
    dst_stem = resolve_reference(dst, root, index)
    if dst_stem is None:
        if not force:
            raise LinkError(
                f"Target '{dst}' does not resolve to a real document. "
                "Use --force to create a dangling edge."
            )
        dst_stem = _normalise_stem(dst)
    try:
        if _declares(src_path, dst_stem):
            return LinkResult(LinkStatus.UNCHANGED, src_stem, dst_stem, dry_run)
        if dry_run:
            return LinkResult(LinkStatus.CREATED, src_stem, dst_stem, dry_run=True)
        added = link_document(root, src_path, dst_stem)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise LinkError(f"Write failed: {exc}") from exc
    status = LinkStatus.CREATED if added else LinkStatus.UNCHANGED
    return LinkResult(status, src_stem, dst_stem)
