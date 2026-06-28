"""Revert mechanism for builtin firmware resources.

Builtin resources (files ending in .builtin.md) are snapshotted during install.
Revert restores the original snapshot content, discarding local edits.
Custom resources cannot be reverted  - they have no canonical original.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from .helpers import atomic_write

logger = logging.getLogger(__name__)

_BUILTIN_SUFFIX = ".builtin.md"
_SNAPSHOT_DIR = "_snapshots"


def is_builtin(filename: str) -> bool:
    """Return ``True`` if *filename* ends with the ``.builtin.md`` suffix.

    Args:
        filename: Resource filename to test.

    Returns:
        ``True`` for builtin resources, ``False`` for custom resources.
    """
    return filename.endswith(_BUILTIN_SUFFIX)


def snapshot_builtins(vaultspec_dir: Path) -> int:
    """Snapshot all .builtin.md files under .vaultspec/ into _snapshots/.

    Called during install to capture the pristine state. Overwrites any
    existing snapshots. The ``_snapshots/`` tree is skipped during the walk
    so snapshot copies (themselves ``.builtin.md`` files) are never
    re-snapshotted now that resources sit directly under the framework root.

    Args:
        vaultspec_dir: The .vaultspec directory.

    Returns:
        Number of files snapshotted.
    """
    snapshot_dir = vaultspec_dir / _SNAPSHOT_DIR

    if not vaultspec_dir.exists():
        return 0

    count = 0
    for builtin in vaultspec_dir.rglob(f"*{_BUILTIN_SUFFIX}"):
        if snapshot_dir in builtin.parents:
            continue
        rel = builtin.relative_to(vaultspec_dir)
        dest = snapshot_dir / rel
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(builtin), str(dest))
        except OSError as exc:
            logger.warning("Failed to snapshot %s: %s", rel, exc)
            continue
        count += 1
        logger.debug("Snapshotted %s", rel)

    # A snapshot refresh is copy-current plus prune-orphans: a builtin retired
    # from the framework must not leave a snapshot behind, or list_modified_builtins
    # reports it ``missing`` forever and builtin_version stays DELETED.
    prune_orphan_snapshots(vaultspec_dir)

    return count


def prune_orphan_snapshots(vaultspec_dir: Path) -> int:
    """Remove snapshots whose live builtin no longer exists under *vaultspec_dir*.

    When a builtin is retired from the framework its install-time snapshot is
    left behind. That makes :func:`list_modified_builtins` report the snapshot as
    ``missing`` and :func:`collect_builtin_version_state` return ``DELETED``
    permanently, with no in-workspace remedy. Pruning the orphan snapshot
    restores a clean version state and keeps the snapshot tree tracking the live
    builtin set. Now-empty snapshot subdirectories are removed afterwards.

    Args:
        vaultspec_dir: The ``.vaultspec`` directory.

    Returns:
        Number of orphan snapshot files removed.
    """
    snapshot_dir = vaultspec_dir / _SNAPSHOT_DIR
    if not snapshot_dir.exists():
        return 0

    removed = 0
    for snapshot in snapshot_dir.rglob(f"*{_BUILTIN_SUFFIX}"):
        rel = snapshot.relative_to(snapshot_dir)
        if (vaultspec_dir / rel).exists():
            continue
        try:
            snapshot.unlink()
            removed += 1
            logger.debug("Pruned orphan snapshot %s", rel)
        except OSError as exc:
            logger.warning("Failed to prune orphan snapshot %s: %s", rel, exc)

    # Remove now-empty snapshot subdirectories, deepest first.
    for directory in sorted(
        (p for p in snapshot_dir.rglob("*") if p.is_dir()),
        key=lambda p: len(p.parts),
        reverse=True,
    ):
        try:
            if not any(directory.iterdir()):
                directory.rmdir()
        except OSError:
            pass

    return removed


def get_snapshot_content(
    vaultspec_dir: Path, category: str, filename: str
) -> str | None:
    """Retrieve the snapshotted content of a builtin resource.

    Args:
        vaultspec_dir: The .vaultspec directory.
        category: Resource subdirectory under .vaultspec/ (e.g., "rules",
            "skills", "agents").
        filename: The builtin filename.

    Returns:
        Original content string, or None if no snapshot exists.
    """
    snapshot_path = vaultspec_dir / _SNAPSHOT_DIR / category / filename
    if not snapshot_path.exists():
        return None
    try:
        return snapshot_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        logger.warning("Failed to read snapshot %s: %s", snapshot_path, e)
        return None


def revert_resource(vaultspec_dir: Path, category: str, filename: str) -> dict:
    """Revert a resource to its snapshotted original.

    Args:
        vaultspec_dir: The .vaultspec directory.
        category: Resource subdirectory under .vaultspec/ (e.g., "rules",
            "skills", "agents").
        filename: The resource name. A bare name or a ``.builtin`` stem is
            resolved to its canonical ``.builtin.md`` form; a name already
            ending in ``.md`` is left as given (so a custom resource still
            fails the builtin guard).

    Returns:
        Dict with "reverted" (bool), "filename" (the resolved name), and
        "reason" (str).
    """
    # Resolve a bare name to the canonical builtin filename. A name that
    # already ends in .md is a fully-qualified resource and is left alone.
    if not filename.endswith(".md"):
        filename += ".md" if filename.endswith(".builtin") else ".builtin.md"

    if not is_builtin(filename):
        return {
            "reverted": False,
            "filename": filename,
            "reason": (
                f"'{filename}' is not a builtin resource; "
                "only *.builtin.md files can be reverted."
            ),
        }

    original = get_snapshot_content(vaultspec_dir, category, filename)
    if original is None:
        return {
            "reverted": False,
            "filename": filename,
            "reason": f"No snapshot found for {category}/{filename}. Was install run?",
        }

    target = vaultspec_dir / category / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(target, original)
    logger.info("Reverted %s/%s to snapshot original.", category, filename)
    return {
        "reverted": True,
        "filename": filename,
        "reason": "Restored to install snapshot.",
    }


def list_modified_builtins(vaultspec_dir: Path) -> list[dict]:
    """List builtin resources that differ from their install-time snapshots.

    Args:
        vaultspec_dir: The ``.vaultspec`` directory to inspect.

    Returns:
        List of dicts with keys ``"category"`` (str), ``"filename"`` (str),
        ``"path"`` (str), and ``"status"``  - one of ``"modified"``,
        ``"missing"``, or ``"ok"``.  Returns an empty list when no snapshots
        exist.
    """
    snapshot_dir = vaultspec_dir / _SNAPSHOT_DIR
    results = []

    if not snapshot_dir.exists():
        return results

    for snapshot in snapshot_dir.rglob(f"*{_BUILTIN_SUFFIX}"):
        rel = snapshot.relative_to(snapshot_dir)
        category = rel.parts[0] if len(rel.parts) > 1 else ""
        current = vaultspec_dir / rel

        if not current.exists():
            status = "missing"
        else:
            try:
                snap_content = snapshot.read_text(encoding="utf-8")
                curr_content = current.read_text(encoding="utf-8")
                status = "modified" if snap_content != curr_content else "ok"
            except (OSError, UnicodeDecodeError):
                status = "modified"

        results.append(
            {
                "category": category,
                "filename": rel.name,
                "path": str(rel),
                "status": status,
            }
        )

    return results
