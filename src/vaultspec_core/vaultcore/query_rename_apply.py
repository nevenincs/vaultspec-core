"""Feature rename apply-with-rollback and the public entry point.

Companion to :mod:`.query_rename`: that module computes the side-effect-free
rename plan, this module applies it through a reverse-journaled
:class:`~vaultspec_core.vaultcore.rename_engine.RenameTransaction` (restoring
the vault byte-for-byte on any mid-apply failure) and exposes
:func:`rename_feature`, the public entry point
(``vaultspec-core vault feature rename``). Split out of :mod:`.query`, which
re-exports :func:`rename_feature` for compatibility.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, TypedDict

from ..core.helpers import atomic_write
from .models import refresh_modified_stamp
from .query_rename import (
    RenameCollision,
    _analyze_cross_feature_links,
    _assert_within_docs,
    _compute_rename_plan,
    _predict_rewrites,
    _rel,
    _RenamePlan,
    _rewrite_feature_tag_block,
    _validate_feature_rename,
)
from .rename_ops import rewrite_incoming_refs

if TYPE_CHECKING:
    from pathlib import Path

    from .query_archive import FeatureCrossLink
    from .rename_engine import RenameTransaction

logger = logging.getLogger(__name__)


class RenameLinkPair(TypedDict):
    """One ``old`` -> ``new`` rel-path or stem pair reported by a rename."""

    old: str
    new: str


class RenameIndexInfo(TypedDict):
    """The pre- and post-rename feature index path pair."""

    old: str | None
    new: str


class RenameApplyResult(TypedDict):
    """Result of the transactional :func:`_apply_rename_plan` half."""

    tag_rewrites: int
    related_rewrites: int
    new_index_path: Path


class FeatureRenameResult(TypedDict):
    """Result of the public :func:`rename_feature` entry point."""

    old: str
    new: str
    renamed_count: int
    paths: list[RenameLinkPair]
    exec_folders: list[RenameLinkPair]
    tag_rewrites: int
    related_rewrites: int
    link_renames: list[RenameLinkPair]
    index: RenameIndexInfo
    cross_links: list[FeatureCrossLink]
    collisions: list[RenameCollision]
    dry_run: bool
    status: str


def _regenerate_feature_index(
    root_dir: Path, new: str, tx: RenameTransaction, index_dir_existed: bool
) -> Path:
    """Regenerate the feature index for *new* from a freshly-built graph.

    A non-cached :class:`~vaultspec_core.graph.VaultGraph` is built so the
    just-renamed (and now ``#new``-tagged) documents are observed.

    Args:
        root_dir: Project root directory.
        new: Normalised target feature name.
        tx: Transaction to record a created index file / directory into.
        index_dir_existed: Whether the index directory existed before apply.

    Returns:
        Path to the regenerated index file.
    """
    from ..config import get_config
    from ..graph import VaultGraph
    from .index import generate_feature_index

    cfg = get_config()
    docs_dir = root_dir / cfg.docs_dir
    index_path = docs_dir / cfg.index_dir / f"{new}.index.md"
    # Refuse to regenerate the index outside the vault: if ``index/`` is a
    # directory symlink pointing elsewhere, the resolved index path escapes
    # ``docs_dir`` and the write would land out of bounds.
    _assert_within_docs(docs_dir, index_path)
    existed = index_path.exists()

    graph = VaultGraph(root_dir, use_cache=False)
    nodes = graph.get_feature_nodes(new)
    path = generate_feature_index(root_dir, new, nodes=nodes)
    if not index_dir_existed and path.parent.is_dir():
        tx.record_created_dir(path.parent)
    if not existed:
        tx.record_created_file(path)
    return path


def _refresh_rename_stamps(
    file_renames: list[tuple[Path, Path]], cascade_paths: set[Path]
) -> None:
    """Refresh the ``modified:`` stamp on every renamed or relinked document.

    Args:
        file_renames: Applied renames; their destinations are stamped.
        cascade_paths: Absolute paths the ``related:`` cascade rewrote.
    """
    from datetime import date

    today = date.today()
    targets: set[Path] = {dst for _src, dst in file_renames} | set(cascade_paths)
    for path in targets:
        if not path.is_file():
            continue
        try:
            text = path.read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        new_text = refresh_modified_stamp(text, today)
        if new_text != text:
            try:
                atomic_write(path, new_text)
            except OSError as exc:
                logger.warning("Failed to refresh modified stamp for %s: %s", path, exc)


def _apply_rename_plan(
    root_dir: Path, plan: _RenamePlan, old: str, new: str
) -> RenameApplyResult:
    """Apply *plan* through a :class:`RenameTransaction`, rolling back on failure.

    The transaction is bound to the docs root (every rename endpoint is
    containment-checked against it) and acquires the docs-domain advisory lock
    for its lifetime; ``advisory_lock`` no-ops when ``.vault/data`` is absent,
    and the transaction never creates it. The caller-supplied snapshot set is
    the whole non-archive docs tree because a feature rename touches all of it.
    Any exception inside the ``with`` block triggers the transaction's reverse
    journal (restoring the vault byte-for-byte) before the wrapped error is
    raised.

    Args:
        root_dir: Project root directory.
        plan: The computed (collision-free) rename plan.
        old: Normalised source feature name.
        new: Normalised target feature name.

    Returns:
        ``{tag_rewrites, related_rewrites, new_index_path}``.

    Raises:
        VaultSpecError: When apply fails; the vault is restored to its
            pre-rename state and the original error is chained.
    """
    from ..config import get_config
    from ..core.exceptions import VaultSpecError
    from .checks._base import CheckResult
    from .rename_engine import (
        RenameTransaction,
        docs_lock_target,
        iter_snapshot_docs,
    )

    cfg = get_config()
    docs_dir = root_dir / cfg.docs_dir
    index_dir = docs_dir / cfg.index_dir
    index_dir_existed = index_dir.exists()
    lock_target = docs_lock_target(docs_dir)

    try:
        with RenameTransaction(docs_dir, lock_target=lock_target) as tx:
            # Snapshot the whole non-archive docs tree under the lock so the
            # reverse journal can restore any moved/rewritten file byte-for-byte.
            tx.snapshot(iter_snapshot_docs(docs_dir))

            # (1) Ensure destination exec folders exist before any record moves.
            for _old_folder, new_folder, _date in plan.exec_dir_renames:
                _assert_within_docs(docs_dir, new_folder)
                if not new_folder.exists():
                    new_folder.mkdir(parents=True, exist_ok=True)
                    tx.record_created_dir(new_folder)

            # (2) Rename every authored doc and exec record. Both endpoints are
            #     containment-checked inside ``tx.rename`` so a symlinked source
            #     or destination can never move a file out of (or into the vault
            #     from) outside the tree.
            for src, dst in plan.file_renames:
                if not tx.rename(src, dst):
                    raise VaultSpecError(
                        f"Filesystem rename failed: {_rel(src, root_dir)} -> "
                        f"{_rel(dst, root_dir)} (destination may already exist)."
                    )

            # (3) Remove now-empty old exec folders.
            for old_folder, _new_folder, _date in plan.exec_dir_renames:
                if old_folder.is_dir() and not any(old_folder.iterdir()):
                    old_folder.rmdir()
                    tx.record_removed_dir(old_folder)

            # (4) Rewrite the #old -> #new tag block in each renamed document.
            tag_rewrites = 0
            for _src, dst in plan.file_renames:
                text = dst.read_bytes().decode("utf-8")
                new_text, changed = _rewrite_feature_tag_block(text, old, new)
                if changed:
                    atomic_write(dst, new_text)
                    tag_rewrites += 1

            # (5) Delete the stale index before the cascade so its soon-discarded
            #     rewrites do not inflate the reported count.
            if plan.index_old_path is not None and plan.index_old_path.exists():
                plan.index_old_path.unlink()

            # (6) Cascade ``related:`` wiki-link rewrites across the vault,
            #     skipping ``_archive`` so a rename never mutates archived
            #     documents - they are out of scope per the ADR and are not
            #     snapshotted for rollback.
            cascade = CheckResult(check_name="feature-rename")
            rewrite_incoming_refs(
                root_dir,
                plan.stem_renames,
                cascade,
                exclude_dirs=frozenset({"_archive"}),
            )
            related_rewrites = cascade.fixed_count
            cascade_paths: set[Path] = set()
            for diag in cascade.diagnostics:
                if diag.path is None:
                    continue
                abs_path = (
                    diag.path if diag.path.is_absolute() else root_dir / diag.path
                )
                cascade_paths.add(abs_path)

            # (7) Regenerate the index for the new feature from a fresh graph.
            new_index_path = _regenerate_feature_index(
                root_dir, new, tx, index_dir_existed
            )

            # (8) Refresh the modified stamp on every renamed or relinked doc.
            _refresh_rename_stamps(plan.file_renames, cascade_paths)

            return {
                "tag_rewrites": tag_rewrites,
                "related_rewrites": related_rewrites,
                "new_index_path": new_index_path,
            }
    except Exception as exc:
        raise VaultSpecError(
            f"Feature rename '{old}' -> '{new}' failed and was rolled back to "
            f"the pre-rename state: {exc}"
        ) from exc


def rename_feature(
    root_dir: Path,
    old: str,
    new: str,
    *,
    dry_run: bool = False,
    force: bool = False,
) -> FeatureRenameResult:
    """Atomically rename a ``#feature`` across every binding surface.

    Rewrites authored document filenames, the exec folder and exec record
    filenames, the ``#feature`` frontmatter tag, ``related:`` wiki-links, and
    the regenerated feature index.  Free-form body prose is never touched.
    The apply path records a reverse journal so that any mid-apply failure
    restores the vault byte-for-byte to its pre-rename state.

    Args:
        root_dir: Project root directory.
        old: Source feature tag (leading ``#`` tolerated).
        new: Target feature tag (leading ``#`` tolerated).
        dry_run: When ``True``, compute and return the full plan without
            mutating anything on disk.
        force: When ``True``, merge the source feature into an existing
            target feature (per-file path collisions still refuse).

    Returns:
        A :class:`FeatureRenameResult` with a canonical ``status``
        (``"unchanged"`` for a dry-run preview, ``"updated"`` once applied).

    Raises:
        VaultSpecError: On any validation failure, a detected destination
            collision, or an apply failure (after rollback). The CLI renders
            a ``"failed"`` envelope from the raised error.
    """
    from ..core.exceptions import VaultSpecError

    old_clean, new_clean, src_docs = _validate_feature_rename(
        root_dir, old, new, force=force
    )
    plan = _compute_rename_plan(root_dir, old_clean, new_clean, src_docs)

    if plan.collisions:
        detail = "; ".join(
            f"{c['destination']} <- {', '.join(c['sources'])} ({c['reason']})"
            for c in plan.collisions
        )
        raise VaultSpecError(
            f"Refusing to rename '{old_clean}' -> '{new_clean}': "
            f"{len(plan.collisions)} destination collision(s): {detail}"
        )

    cross_links = _analyze_cross_feature_links(root_dir, src_docs, old_clean)

    paths: list[RenameLinkPair] = [
        {"old": _rel(src, root_dir), "new": _rel(dst, root_dir)}
        for src, dst in plan.file_renames
    ]
    exec_folders: list[RenameLinkPair] = [
        {"old": _rel(old_folder, root_dir), "new": _rel(new_folder, root_dir)}
        for old_folder, new_folder, _date in plan.exec_dir_renames
    ]
    link_renames: list[RenameLinkPair] = [
        {"old": o, "new": n} for o, n in plan.stem_renames
    ]
    index_info: RenameIndexInfo = {
        "old": _rel(plan.index_old_path, root_dir)
        if plan.index_old_path is not None
        else None,
        "new": _rel(plan.index_new_path, root_dir),
    }

    if dry_run:
        predicted_tag, predicted_related = _predict_rewrites(
            root_dir, plan, old_clean, new_clean
        )
        return {
            "old": old_clean,
            "new": new_clean,
            "renamed_count": len(plan.file_renames),
            "paths": paths,
            "exec_folders": exec_folders,
            "tag_rewrites": predicted_tag,
            "related_rewrites": predicted_related,
            "link_renames": link_renames,
            "index": index_info,
            "cross_links": cross_links,
            "collisions": plan.collisions,
            "dry_run": True,
            "status": "unchanged",
        }

    applied = _apply_rename_plan(root_dir, plan, old_clean, new_clean)
    index_info["new"] = _rel(applied["new_index_path"], root_dir)

    return {
        "old": old_clean,
        "new": new_clean,
        "renamed_count": len(plan.file_renames),
        "paths": paths,
        "exec_folders": exec_folders,
        "tag_rewrites": applied["tag_rewrites"],
        "related_rewrites": applied["related_rewrites"],
        "link_renames": link_renames,
        "index": index_info,
        "cross_links": cross_links,
        "collisions": [],
        "dry_run": False,
        "status": "updated",
    }
