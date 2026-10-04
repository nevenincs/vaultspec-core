"""Validate and open regular corpus files within a workspace's docs root."""

from __future__ import annotations

import os
import stat
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path
    from typing import BinaryIO


class UnsafeDocumentError(OSError):
    """A document path is redirected, outside its vault, or not a regular file."""


def _is_redirected(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def corpus_path_info(
    path: Path, root_dir: Path, *, directory: bool = False
) -> tuple[Path, os.stat_result]:
    """Require real components and resolved containment below the docs root.

    The workspace itself may be named through an alias. An explicitly configured
    absolute external docs directory uses its parent as the trusted anchor,
    matching configuration validation. Every component below the anchor must
    be real. Callers retain lexical paths for classification and responses.
    """
    from ..config import get_config

    root = root_dir.absolute()
    configured_docs = get_config().docs_dir
    docs = root / configured_docs
    external = os.path.isabs(configured_docs) and not docs.is_relative_to(root)
    anchor = docs.parent if external else root
    candidate = path.absolute()
    try:
        docs_relative = docs.relative_to(anchor)
        relative = candidate.relative_to(docs)
        if not docs_relative.parts or ".." in (*docs_relative.parts, *relative.parts):
            raise ValueError("invalid corpus path")
    except ValueError as exc:
        raise UnsafeDocumentError(f"Document path escapes vault: {path}") from exc

    current = anchor
    info = anchor.lstat()
    for component in (*docs_relative.parts, *relative.parts):
        current /= component
        info = current.lstat()
        if _is_redirected(info):
            raise UnsafeDocumentError(f"Document path is redirected: {current}")
        if current != candidate and not stat.S_ISDIR(info.st_mode):
            raise UnsafeDocumentError(f"Document parent is not a directory: {current}")
    expected_type = stat.S_ISDIR if directory else stat.S_ISREG
    if not expected_type(info.st_mode):
        raise UnsafeDocumentError(f"Invalid corpus entry type: {path}")
    resolved_docs = docs.resolve(strict=True)
    resolved = candidate.resolve(strict=True)
    if not resolved_docs.is_relative_to(anchor.resolve(strict=True)) or (
        not resolved.is_relative_to(resolved_docs)
    ):
        raise UnsafeDocumentError(f"Resolved document path escapes vault: {path}")
    return resolved, info


def is_corpus_path(path: Path, root_dir: Path, *, directory: bool = False) -> bool:
    """Return whether an existing corpus entry is safe to enumerate."""
    try:
        corpus_path_info(path, root_dir, directory=directory)
    except OSError:
        return False
    return True


def _document_info(path: Path, root_dir: Path | None) -> tuple[Path, os.stat_result]:
    if root_dir is not None:
        return corpus_path_info(path, root_dir)
    info = path.lstat()
    if _is_redirected(info) or not stat.S_ISREG(info.st_mode):
        raise UnsafeDocumentError(f"Document must be a regular file: {path}")
    return path.resolve(strict=True), info


@contextmanager
def open_document(path: Path, *, root_dir: Path | None = None) -> Generator[BinaryIO]:
    """Check descriptor identity and revalidate the path before yielding bytes.

    No-follow and nonblocking flags prevent a final link or FIFO replacement
    from being followed or hanging. Comparing the opened descriptor with the
    validated file also detects redirected ancestors. Reads use this pinned
    descriptor after rechecking the original path.
    """
    resolved, info = _document_info(path, root_dir)
    flags = (
        os.O_RDONLY
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
        | getattr(os, "O_BINARY", 0)
    )
    try:
        descriptor = os.open(resolved, flags)
    except OSError:
        # An open failure caused by a late link/type replacement must retain
        # the unsafe-path error, so consumers cannot emit a resource URI for it.
        _document_info(path, root_dir)
        raise
    with os.fdopen(descriptor, "rb") as source:
        opened = os.fstat(source.fileno())
        if not stat.S_ISREG(opened.st_mode) or not os.path.samestat(info, opened):
            raise UnsafeDocumentError(f"Document changed while opening: {path}")
        checked, latest = _document_info(path, root_dir)
        if checked != resolved or not os.path.samestat(latest, opened):
            raise UnsafeDocumentError(f"Document changed while opening: {path}")
        yield source
