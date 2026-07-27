"""Atomic archival of an explicit set of live vault documents."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ..config import get_config
from ..core.exceptions import VaultSpecError
from .checks.exec_mapping import _link_stem
from .parser import parse_vault_metadata
from .rename_engine import RenameTransaction, _assert_within, docs_lock_target

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = [
    "ArchiveDocumentsError",
    "ArchiveDocumentsResult",
    "archive_documents",
]


class ArchiveDocumentsError(VaultSpecError):
    """Raised when an explicit batch archive cannot safely proceed."""


@dataclass(frozen=True)
class ArchiveDocumentsResult:
    """The paths archived, or validated for archival by a dry run."""

    status: str
    archived_paths: tuple[Path, ...]
    cross_link_paths: tuple[Path, ...]
    dry_run: bool

    @property
    def archived_count(self) -> int:
        """Return the number of documents in the explicit archive batch."""
        return len(self.archived_paths)

    @property
    def paths(self) -> tuple[Path, ...]:
        """Compatibility name for the destination paths."""
        return self.archived_paths

    def to_dict(self) -> dict[str, object]:
        """Return a portable, JSON-ready representation."""
        return {
            "status": self.status,
            "archived_count": self.archived_count,
            "paths": [path.as_posix() for path in self.archived_paths],
            "cross_link_paths": [path.as_posix() for path in self.cross_link_paths],
            "dry_run": self.dry_run,
        }


@dataclass(frozen=True)
class _ArchiveMove:
    source: Path
    destination: Path
    source_relative: Path


def archive_documents(
    root_dir: Path,
    relative_paths: Iterable[str | Path],
    *,
    dry_run: bool = False,
) -> ArchiveDocumentsResult:
    """Archive explicit project-relative ``.vault`` document paths as one batch.

    Every input must be a relative path beginning within the configured vault
    directory. Each document moves to ``.vault/_archive/<vault-relative-path>``.
    Preflight rejects every unsafe source or destination before the first move;
    an apply runs under the normal docs-domain lock and rolls back on failure.
    """
    root = root_dir.resolve()
    docs_dir = root / get_config().docs_dir
    _assert_docs_dir(root, docs_dir)

    supplied = tuple(relative_paths)
    if dry_run:
        moves = _preflight(root, docs_dir, supplied)
        cross_links = _cross_link_paths(root, docs_dir, moves)
        return _result(root, moves, cross_links, dry_run=True)

    runtime_dir = docs_dir / "data"
    if runtime_dir.is_symlink():
        raise ArchiveDocumentsError(
            f"Vault runtime directory must not be a symlink: {runtime_dir}"
        )
    runtime_dir.mkdir(exist_ok=True)
    if not runtime_dir.is_dir():
        raise ArchiveDocumentsError(
            f"Vault runtime path is not a directory: {runtime_dir}"
        )

    with RenameTransaction(docs_dir, lock_target=docs_lock_target(docs_dir)) as tx:
        # Re-run the whole preflight while holding the common docs lock. This
        # closes the gap between validation and the first destructive rename.
        moves = _preflight(root, docs_dir, supplied)
        cross_links = _cross_link_paths(root, docs_dir, moves)
        tx.snapshot(move.source for move in moves)
        for move in moves:
            _create_archive_parent(tx, docs_dir, move.destination.parent)
            _require_regular_document(move.source)
            try:
                moved = tx.rename(move.source, move.destination)
            except OSError as exc:
                raise ArchiveDocumentsError(
                    f"Archive move failed: {move.source} -> {move.destination}: {exc}"
                ) from exc
            if not moved:
                raise ArchiveDocumentsError(
                    "Archive move was refused without replacing a destination: "
                    f"{move.source} -> {move.destination}"
                )

    return _result(root, moves, cross_links, dry_run=False)


def _assert_docs_dir(root: Path, docs_dir: Path) -> None:
    if docs_dir.is_symlink() or not docs_dir.is_dir():
        raise ArchiveDocumentsError(
            f"Vault document directory must be a real directory: {docs_dir}"
        )
    try:
        docs_dir.relative_to(root)
        docs_dir.resolve(strict=False).relative_to(root)
    except ValueError as exc:
        raise ArchiveDocumentsError(
            f"Configured vault directory escapes the project root: {docs_dir}"
        ) from exc


def _preflight(
    root: Path, docs_dir: Path, relative_paths: tuple[str | Path, ...]
) -> tuple[_ArchiveMove, ...]:
    if not relative_paths:
        raise ArchiveDocumentsError("Archive requires at least one document path.")

    moves: list[_ArchiveMove] = []
    seen_sources: set[Path] = set()
    seen_destinations: set[Path] = set()
    for value in relative_paths:
        source, source_relative = _resolve_source(root, docs_dir, value)
        destination = docs_dir / "_archive" / source_relative
        _assert_within(docs_dir, destination)
        if source in seen_sources:
            raise ArchiveDocumentsError(f"Duplicate archive source: {source}")
        if destination in seen_destinations:
            raise ArchiveDocumentsError(f"Archive destination collision: {destination}")
        if destination.exists() or destination.is_symlink():
            raise ArchiveDocumentsError(
                f"Archive destination already exists: {destination}"
            )
        _require_safe_archive_parent(docs_dir, destination.parent)
        seen_sources.add(source)
        seen_destinations.add(destination)
        moves.append(_ArchiveMove(source, destination, source_relative))
    return tuple(moves)


def _resolve_source(root: Path, docs_dir: Path, value: str | Path) -> tuple[Path, Path]:
    relative = Path(value)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise ArchiveDocumentsError(
            f"Archive path must be project-relative and confined to .vault: {value}"
        )
    raw_source = root / relative
    try:
        vault_relative = raw_source.relative_to(docs_dir)
    except ValueError as exc:
        raise ArchiveDocumentsError(
            f"Archive path must be under {docs_dir}: {relative}"
        ) from exc
    if not vault_relative.parts or vault_relative.parts[0] == "_archive":
        raise ArchiveDocumentsError(
            f"Archive source must be live and outside _archive: {relative}"
        )
    if raw_source.suffix.lower() != ".md":
        raise ArchiveDocumentsError(
            f"Archive source must be a vault Markdown document: {relative}"
        )
    _require_no_symlink_components(docs_dir, raw_source)
    source = raw_source.resolve(strict=False)
    _assert_within(docs_dir, source)
    _require_regular_document(source)
    return source, vault_relative


def _require_regular_document(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise ArchiveDocumentsError(f"Archive source is not a regular file: {path}")
    try:
        path.read_bytes()
    except OSError as exc:
        raise ArchiveDocumentsError(
            f"Cannot read archive source {path}: {exc}"
        ) from exc


def _require_no_symlink_components(docs_dir: Path, path: Path) -> None:
    try:
        relative = path.relative_to(docs_dir)
    except ValueError as exc:
        raise ArchiveDocumentsError(f"Archive source escapes vault: {path}") from exc
    current = docs_dir
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ArchiveDocumentsError(
                f"Archive source contains a symlink component: {current}"
            )


def _require_safe_archive_parent(docs_dir: Path, parent: Path) -> None:
    _assert_within(docs_dir, parent)
    current = docs_dir
    relative = parent.relative_to(docs_dir)
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ArchiveDocumentsError(
                f"Archive destination parent must not be a symlink: {current}"
            )
        if current.exists() and not current.is_dir():
            raise ArchiveDocumentsError(
                f"Archive destination parent is not a directory: {current}"
            )


def _create_archive_parent(
    transaction: RenameTransaction, docs_dir: Path, parent: Path
) -> None:
    _require_safe_archive_parent(docs_dir, parent)
    missing: list[Path] = []
    current = parent
    while current != docs_dir and not current.exists():
        missing.append(current)
        current = current.parent
    for directory in reversed(missing):
        directory.mkdir()
        transaction.record_created_dir(directory)


def _cross_link_paths(
    root: Path, docs_dir: Path, moves: tuple[_ArchiveMove, ...]
) -> tuple[Path, ...]:
    archived_stems = {move.source.stem for move in moves}
    source_paths = {move.source for move in moves}
    linked: list[Path] = []
    for path in docs_dir.rglob("*.md"):
        try:
            relative = path.relative_to(docs_dir)
        except ValueError:
            continue
        if path in source_paths or "_archive" in relative.parts:
            continue
        if path.is_symlink() or not path.is_file():
            continue
        try:
            metadata, _body = parse_vault_metadata(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValueError):
            continue
        if any(_link_stem(link) in archived_stems for link in metadata.related):
            linked.append(path.relative_to(root))
    return tuple(sorted(linked))


def _result(
    root: Path,
    moves: tuple[_ArchiveMove, ...],
    cross_links: tuple[Path, ...],
    *,
    dry_run: bool,
) -> ArchiveDocumentsResult:
    return ArchiveDocumentsResult(
        status="unchanged" if dry_run else "updated",
        archived_paths=tuple(move.destination.relative_to(root) for move in moves),
        cross_link_paths=cross_links,
        dry_run=dry_run,
    )
