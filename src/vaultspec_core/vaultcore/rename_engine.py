"""Shared transactional rename engine for vaultspec CRUD surfaces.

This module holds the reusable transaction mechanics that every rename/move
surface in the CLI converges onto: a root-generalized containment guard, a
symlink-safe byte restore, and a :class:`RenameTransaction` context manager
that journals each mutation and rolls the managed root back byte-for-byte on
any failure while holding a per-domain advisory lock for its lifetime.

The mechanics are extracted verbatim from the hardened ``rename_feature``
backend (formerly the bespoke ``_RenameJournal`` / ``_snapshot_docs`` /
``_rollback_rename`` helpers in :mod:`vaultspec_core.vaultcore.query`) so the
behavior every caller inherits is identical to the one the feature-rename
adversarial suites already pin. The single generalization is that containment
and the snapshot set are parameterized by the caller's managed root rather than
hardcoded to the docs directory, so the same engine protects renames under
``.vault/`` and under ``.vaultspec/``.
"""

from __future__ import annotations

import contextlib
import logging
import shutil
from typing import TYPE_CHECKING

from ..core.helpers import advisory_lock
from .rename_ops import rename_document_path

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator
    from pathlib import Path

logger = logging.getLogger(__name__)


def _assert_within(managed_root: Path, path: Path) -> Path:
    """Return *path* iff its real location is inside *managed_root*, else raise.

    Resolves every symlink and ``..`` segment in *path* (and in any existing
    ancestor of a not-yet-created destination) and refuses the operation when
    the result escapes the managed tree.  This is the containment backstop that
    prevents a rename from reading, writing, moving, or deleting a file whose
    true location is outside the managed root - including the case where a
    subdirectory or a document is itself a symlink pointing outside the
    project.

    Args:
        managed_root: The root the rename is allowed to operate within
            (e.g. the vault document root, or a ``.vaultspec`` resource root).
        path: A candidate source or destination path inside the rename plan.

    Returns:
        *path* unchanged when it is contained.

    Raises:
        VaultSpecError: When *path* resolves outside *managed_root*.
    """
    from ..core.exceptions import VaultSpecError

    real_docs = managed_root.resolve(strict=False)
    real_path = path.resolve(strict=False)
    if real_path != real_docs and real_docs not in real_path.parents:
        raise VaultSpecError(
            "Refusing to operate on a path outside the managed directory tree "
            f"(possible symlink or traversal escape): {path}"
        )
    return path


def _safe_restore_bytes(path: Path, original: bytes) -> None:
    """Restore *original* bytes to *path* without writing through a symlink.

    A symlinked rollback target is unlinked first so the bytes land on a
    fresh regular file at the in-vault path rather than following the link
    to an out-of-bounds destination.
    """
    if path.is_symlink():
        path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(original)


def docs_lock_target(docs_dir: Path) -> Path:
    """Return the advisory-lock target serializing ``.vault`` docs-domain renames.

    The value is the argument to :func:`~vaultspec_core.core.helpers.advisory_lock`,
    which appends ``.lock`` to derive the OS sentinel - here
    ``<docs_dir>/data/.vault.lock`` (the ``data/`` subtree is already gitignored, so
    no lock file is committed). Every docs-domain mutator (feature rename, document
    rename, the structure-rename cascade) MUST pass this exact value so they
    serialize on one sentinel; ``advisory_lock`` no-ops when ``data/`` is absent.
    """
    return docs_dir / "data" / ".vault"


def resource_lock_target(vaultspec_dir: Path) -> Path:
    """Return the advisory-lock target serializing ``.vaultspec`` resource renames.

    The OS sentinel is ``<vaultspec_dir>/.resources.lock`` (``.vaultspec/*.lock`` is
    already gitignored). Every resource-domain mutator (resource rename, hook rename)
    MUST pass this exact value to serialize on one sentinel.
    """
    return vaultspec_dir / ".resources"


def iter_snapshot_docs(managed_root: Path) -> Iterator[Path]:
    """Yield every non-archive ``*.md`` under *managed_root* for snapshotting.

    This is the canonical transaction-snapshot basis shared by every docs-domain
    rename: every ``*.md`` under the managed root except those inside an
    ``_archive`` subtree or any dot-prefixed directory (``.obsidian``,
    ``.trash``, ...). The set is handed to
    :meth:`RenameTransaction.snapshot`, which applies the per-file
    symlink/non-file skip and read-failure handling.

    Both the feature rename (whole-tree mutation) and the single-document rename
    (file move plus ``related:`` cascade) snapshot this exact set so the rollback
    journal is a guaranteed superset of what the apply can mutate: the
    ``related:`` cascade
    (:func:`~vaultspec_core.vaultcore.rename_ops.rewrite_incoming_refs`) also
    excludes ``_archive`` and dot-prefixed directories, so a document the cascade
    can rewrite is always one this iterator captures - and an archived or hidden
    document is never rewritten *nor* snapshotted. Deriving the snapshot from a
    stale graph cache instead would risk missing a rewritten doc and leaving the
    rollback journal incomplete.

    Args:
        managed_root: The vault document root (``<root>/<docs_dir>``).

    Yields:
        Each candidate document path, in ``rglob`` order.
    """
    if not managed_root.is_dir():
        return
    for md in managed_root.rglob("*.md"):
        try:
            rel_parts = md.relative_to(managed_root).parts
        except ValueError:
            continue
        if any(p == "_archive" or p.startswith(".") for p in rel_parts):
            continue
        yield md


class RenameTransaction:
    """A reverse-journaled, lock-protected rename transaction.

    Used as a context manager, it acquires a per-domain advisory lock for its
    lifetime (when a ``lock_target`` is supplied) and journals every mutation
    the caller funnels through it.  If an exception propagates out of the
    ``with`` block the journal is walked in reverse to restore the managed root
    byte-for-byte to its pre-transaction state, then the exception is allowed to
    propagate unchanged; on clean exit the lock is released and nothing is
    rolled back.

    The journal field semantics mirror the former ``_RenameJournal`` exactly so
    the rollback ordering is identical to the hardened feature-rename backend:

    Attributes:
        managed_root: The root every :meth:`rename` endpoint is contained to.
        lock_target: The advisory-lock target acquired for the transaction's
            lifetime, or ``None`` to run without a lock.  ``advisory_lock``
            skips locking when the target's parent directory is absent, and the
            transaction never creates that parent.
        file_renames: ``(src, dst)`` renames actually applied, in order.
        created_dirs: Directories created during apply.
        removed_dirs: Directories removed once emptied during apply.
        created_files: Files created during apply.
        snapshots: Original bytes of every snapshotted file, keyed by path.
    """

    def __init__(self, managed_root: Path, *, lock_target: Path | None = None) -> None:
        self.managed_root = managed_root
        self.lock_target = lock_target
        self._stack = contextlib.ExitStack()
        self.file_renames: list[tuple[Path, Path]] = []
        self.created_dirs: list[Path] = []
        self.removed_dirs: list[Path] = []
        self.created_files: list[Path] = []
        self.snapshots: dict[Path, bytes] = {}

    def __enter__(self) -> RenameTransaction:
        """Acquire the domain advisory lock (if any) and return ``self``."""
        if self.lock_target is not None:
            self._stack.enter_context(advisory_lock(self.lock_target))
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> bool:
        """Roll back on a propagating exception, then release the lock.

        Rollback runs while the lock is still held so the restore is serialized
        against other mutators in the domain; the lock is released afterwards.
        The exception is never suppressed.
        """
        try:
            if exc_type is not None:
                self._rollback()
        finally:
            self._stack.close()
        return False

    def snapshot(self, paths: Iterable[Path]) -> None:
        """Record the original bytes of a caller-supplied file set.

        The caller decides the participating set; the engine never rglobs a
        root.  Per-file behavior matches the former ``_snapshot_docs``:
        symlinks and non-files are skipped (a symlinked file is not a
        legitimate managed document and snapshotting it would pull an
        out-of-bounds target's bytes into the rollback journal), and an
        unreadable file logs a warning rather than aborting.

        Args:
            paths: The files whose pre-transaction bytes to capture.
        """
        for path in paths:
            if path.is_symlink() or not path.is_file():
                continue
            try:
                self.snapshots[path] = path.read_bytes()
            except OSError as exc:
                logger.warning("Could not snapshot %s for rollback: %s", path, exc)

    def rename(self, src: Path, dst: Path) -> bool:
        """Containment-check both endpoints, rename, and journal on success.

        Args:
            src: Source path (contained to :attr:`managed_root`).
            dst: Destination path (contained to :attr:`managed_root`).

        Returns:
            The result of
            :func:`~vaultspec_core.vaultcore.rename_ops.rename_document_path`; a
            journal entry is recorded only when the rename succeeds.

        Raises:
            VaultSpecError: When either endpoint resolves outside the root.
        """
        _assert_within(self.managed_root, src)
        _assert_within(self.managed_root, dst)
        ok = rename_document_path(src, dst)
        if ok:
            self.file_renames.append((src, dst))
        return ok

    def record_created_file(self, path: Path) -> None:
        """Journal a file created during apply (deleted first on rollback)."""
        self.created_files.append(path)

    def record_created_dir(self, path: Path) -> None:
        """Journal a directory created during apply (dropped on rollback)."""
        self.created_dirs.append(path)

    def record_removed_dir(self, path: Path) -> None:
        """Journal a directory removed during apply (recreated on rollback)."""
        self.removed_dirs.append(path)

    def _rollback(self) -> None:
        """Walk the journal in reverse to restore the pre-transaction state.

        The order is deliberate and identical to the former
        ``_rollback_rename``: delete created files first, recreate removed
        directories so renamed records have a home to return to, reverse the
        file renames (LIFO), drop any directories created during apply, and
        finally restore every snapshot's original bytes (which also recreates
        any deleted file captured in the snapshot set).
        """
        for path in self.created_files:
            with contextlib.suppress(OSError):
                if path.is_file():
                    path.unlink()

        for directory in self.removed_dirs:
            with contextlib.suppress(OSError):
                directory.mkdir(parents=True, exist_ok=True)

        for src, dst in reversed(self.file_renames):
            if not dst.exists():
                continue
            if rename_document_path(dst, src):
                continue
            with contextlib.suppress(OSError):
                shutil.move(str(dst), str(src))

        for directory in reversed(self.created_dirs):
            with contextlib.suppress(OSError):
                if directory.is_dir() and not any(directory.iterdir()):
                    directory.rmdir()

        for path, original in self.snapshots.items():
            try:
                # If the key became a symlink since the snapshot, restore through
                # a fresh regular file (never write through the link to an
                # out-of-bounds target). Otherwise restore only when content
                # drifted. ``is_symlink()`` is checked first so the short-circuit
                # avoids a symlink-following ``read_bytes()``.
                if (
                    path.is_symlink()
                    or not path.exists()
                    or path.read_bytes() != original
                ):
                    _safe_restore_bytes(path, original)
            except OSError as exc:
                logger.warning("Rollback could not restore %s: %s", path, exc)
