"""Validate and open regular corpus files within a workspace's docs root."""

from __future__ import annotations

import os
import stat
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path
    from typing import BinaryIO


class UnsafeDocumentError(OSError):
    """A document path is redirected, outside its vault, or not a regular file."""


@dataclass(frozen=True)
class _CorpusRoot:
    root: Path
    docs: str
    resolved_anchor: Path
    observed: dict[Path, tuple[os.stat_result, Path]] = field(default_factory=dict)


_CORPUS_ROOT: ContextVar[_CorpusRoot | None] = ContextVar(
    "corpus_read_root", default=None
)


@contextmanager
def corpus_read_scope(root_dir: Path) -> Generator[None]:
    """Resolve corpus configuration once; keep validating every file access."""
    from ..config.read_scope import config_read_scope

    root = root_dir.absolute()
    active = _CORPUS_ROOT.get()
    if active is not None and active.root == root:
        yield
        return
    with config_read_scope(root) as config:
        configured_docs = config.docs_dir
        docs = root / configured_docs
        external = os.path.isabs(configured_docs) and not docs.is_relative_to(root)
        anchor = docs.parent if external else root
        resolved_anchor = anchor.resolve()
        if os.name == "nt":
            from .windows_paths import normalise_path

            resolved_anchor = normalise_path(str(resolved_anchor))
        token = _CORPUS_ROOT.set(_CorpusRoot(root, configured_docs, resolved_anchor))
        try:
            yield
        finally:
            _CORPUS_ROOT.reset(token)


def _is_redirected(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def _corpus_location(
    path: Path, root_dir: Path
) -> tuple[Path, tuple[str, ...], Path | None]:
    """Validate lexical containment and derive the pinned canonical spelling."""
    from ..config import get_config

    root = root_dir.absolute()
    active = _CORPUS_ROOT.get()
    if active is not None and active.root != root:
        active = None
    configured_docs = active.docs if active is not None else get_config().docs_dir
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
    parts = (*docs_relative.parts, *relative.parts)
    expected = active.resolved_anchor.joinpath(*parts) if active is not None else None
    return anchor, parts, expected


def corpus_path_info(
    path: Path, root_dir: Path, *, directory: bool = False
) -> tuple[Path, os.stat_result]:
    """Require real components and resolved containment below the docs root.

    Workspace aliases and explicitly configured external docs roots are allowed;
    entries beneath the trusted anchor may not be redirected.
    """
    anchor, parts, expected = _corpus_location(path, root_dir)
    candidate = path.absolute()

    if expected is not None:
        # Resolving to the exact rooted spelling detects redirected ancestors,
        # including links back inside the corpus. Rechecking each ancestor with
        # lstat separately adds one filesystem round trip per depth per access.
        info = candidate.lstat()
        expected_type = stat.S_ISDIR if directory else stat.S_ISREG
        if _is_redirected(info) or not expected_type(info.st_mode):
            raise UnsafeDocumentError(f"Invalid or redirected corpus entry: {path}")
        if os.name == "nt":
            from .windows_paths import resolved_path

            resolved = resolved_path(candidate)
        else:
            resolved = candidate.resolve(strict=True)
        if resolved != expected:
            raise UnsafeDocumentError(f"Resolved document path escapes vault: {path}")
        active = _CORPUS_ROOT.get()
        if not directory and active is not None:
            active.observed[candidate] = (info, expected)
        return resolved, info

    current = anchor
    info = anchor.lstat()
    for component in parts:
        current /= component
        info = current.lstat()
        if _is_redirected(info):
            raise UnsafeDocumentError(f"Document path is redirected: {current}")
        if current != candidate and not stat.S_ISDIR(info.st_mode):
            raise UnsafeDocumentError(f"Document parent is not a directory: {current}")
    expected_type = stat.S_ISDIR if directory else stat.S_ISREG
    if not expected_type(info.st_mode):
        raise UnsafeDocumentError(f"Invalid corpus entry type: {path}")
    resolved_anchor = anchor.resolve(strict=True)
    resolved = candidate.resolve(strict=True)
    if resolved != resolved_anchor.joinpath(*parts):
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
    expected: Path | None = None
    prior: tuple[os.stat_result, Path] | None = None
    if os.name == "nt" and root_dir is not None:
        active = _CORPUS_ROOT.get()
        if active is not None and active.root == root_dir.absolute():
            prior = active.observed.get(path.absolute())
        if prior is None:
            _, _, expected = _corpus_location(path, root_dir)
        else:
            expected = prior[1]
    if expected is None:
        resolved, info = _document_info(path, root_dir)
    else:
        resolved, info = path, prior[0] if prior is not None else path.lstat()
        if _is_redirected(info) or not stat.S_ISREG(info.st_mode):
            raise UnsafeDocumentError(f"Invalid or redirected corpus entry: {path}")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
        | getattr(os, "O_BINARY", 0)
    )
    try:
        if expected is not None:
            from .windows_paths import open_file_nofollow

            descriptor = open_file_nofollow(resolved)
        else:
            descriptor = os.open(resolved, flags)
    except OSError:
        # An open failure caused by a late link/type replacement must retain
        # the unsafe-path error, so consumers cannot emit a resource URI for it.
        _document_info(path, root_dir)
        raise
    with os.fdopen(descriptor, "rb") as source:
        opened = os.fstat(source.fileno())
        if (
            _is_redirected(opened)
            or not stat.S_ISREG(opened.st_mode)
            or not os.path.samestat(info, opened)
        ):
            raise UnsafeDocumentError(f"Document changed while opening: {path}")
        if expected is None:
            checked, latest = _document_info(path, root_dir)
            same_path = checked == resolved
        else:
            from .windows_paths import opened_file_path

            latest = path.lstat()
            if opened_file_path(source.fileno()) != expected:
                raise UnsafeDocumentError(
                    f"Resolved document path escapes vault: {path}"
                )
            same_path = not _is_redirected(latest)
        if not same_path or not os.path.samestat(latest, opened):
            raise UnsafeDocumentError(f"Document changed while opening: {path}")
        yield source
