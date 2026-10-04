"""Preflight migration trees without following repository-controlled links."""

from __future__ import annotations

import stat
from typing import TYPE_CHECKING

from . import MigrationError

if TYPE_CHECKING:
    from pathlib import Path


def check_path(workspace: Path, path: Path) -> None:
    """Reject links in every component and paths outside the workspace.

    Missing destinations are valid, but their existing ancestors must be real
    directories. Resolve the workspace itself so invocation through an alias
    remains supported. Windows junctions are reparse points, not symlinks.
    """
    try:
        root = workspace.resolve()
        candidate = root / path.relative_to(workspace)
        if ".." in candidate.relative_to(root).parts:
            raise MigrationError(f"Migration path escapes workspace: {path}")
        for component in (*reversed(candidate.parents), candidate):
            if component == root or root not in component.parents:
                continue
            try:
                info = component.lstat()
            except FileNotFoundError:
                continue
            if stat.S_ISLNK(info.st_mode) or (
                getattr(info, "st_file_attributes", 0)
                & stat.FILE_ATTRIBUTE_REPARSE_POINT
            ):
                raise MigrationError(f"Migration refuses linked path: {component}")
        if not candidate.resolve().is_relative_to(root):
            raise MigrationError(f"Migration path escapes workspace: {path}")
    except (OSError, ValueError) as exc:
        raise MigrationError(f"Cannot validate migration path {path}: {exc}") from exc


def check_tree(
    workspace: Path,
    path: Path,
    *,
    skip_linked_indexes: bool = False,
    excluded_dirs: frozenset[str] = frozenset(),
) -> None:
    """Validate all existing sources and destinations before any mutation.

    Index relocation already skips symlinked source indexes. Preserve that
    behavior; its destination tree must still be validated without this option.
    Excluded corpus subtrees are left untouched; snapshot writers check their
    destination root separately instead of inspecting old backups.
    The traversal uses lstat before enumerating each directory, including empty
    and dangling links that glob or exists would otherwise overlook.
    """
    pending = [path]
    while pending:
        current = pending.pop()
        if current != path and current.name in excluded_dirs:
            continue
        try:
            info = current.lstat()
        except FileNotFoundError:
            check_path(workspace, current)
            continue
        except OSError as exc:
            raise MigrationError(
                f"Cannot inspect migration path {current}: {exc}"
            ) from exc
        if (
            skip_linked_indexes
            and stat.S_ISLNK(info.st_mode)
            and current.name.endswith(".index.md")
            and not current.is_dir()
        ):
            continue
        check_path(workspace, current)
        if stat.S_ISDIR(info.st_mode):
            try:
                pending.extend(current.iterdir())
            except OSError as exc:
                raise MigrationError(
                    f"Cannot enumerate migration directory {current}: {exc}"
                ) from exc
