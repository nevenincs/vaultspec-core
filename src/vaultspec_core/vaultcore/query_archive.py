"""Feature archive/unarchive (``vaultspec-core vault feature archive|unarchive``).

Moves a feature's documents into and out of ``.vault/_archive/``, preserving
the per-type subdirectory structure. Split out of :mod:`.query`, which
re-exports :func:`archive_feature` and :func:`unarchive_feature` for
compatibility.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, TypedDict

from ..core.document_io import read_document_text
from .batch_archive import (
    _assert_docs_dir,
    _assert_runtime_dir,
    _iter_safe_documents,
    _require_no_symlink_components,
    archive_documents,
    restore_documents,
)
from .query_listing import feature_from_tags_or_meta, list_documents

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


class FeatureCrossLink(TypedDict):
    """One incoming cross-feature link surfaced during archive/rename."""

    source: str
    target: str
    source_path: str


class FeatureArchiveResult(TypedDict):
    """Result of :func:`archive_feature`."""

    archived_count: int
    paths: list[str]
    cross_links: list[FeatureCrossLink]
    dry_run: bool


class FeatureUnarchiveResult(TypedDict):
    """Result of :func:`unarchive_feature`."""

    unarchived_count: int
    paths: list[str]
    dry_run: bool


def archive_feature(
    root_dir: Path, feature: str, dry_run: bool = False
) -> FeatureArchiveResult:
    """Move all documents for a feature into ``.vault/_archive/``.

    Preserves the per-type subdirectory structure under the archive folder.

    Args:
        root_dir: Project root directory.
        feature: Feature name to archive (leading ``#`` is stripped).
        dry_run: Preview planned changes.

    Returns:
        A :class:`FeatureArchiveResult`.
    """
    from ..config import get_config
    from ..core.exceptions import VaultSpecError

    feature = feature.strip().lstrip("#").strip()
    if not feature:
        raise VaultSpecError(
            "A feature tag is required to archive. Refusing to run with an "
            "empty tag, which would match and archive every document.",
        )

    cfg = get_config()
    root_dir = root_dir.resolve()
    vault_dir = root_dir / cfg.docs_dir
    _require_no_symlink_components(root_dir, vault_dir)
    if not vault_dir.exists():
        raise VaultSpecError(f"Feature tag '{feature}' matches zero documents.")
    _assert_docs_dir(root_dir, vault_dir)
    _assert_runtime_dir(vault_dir)
    # Validate the corpus before the graph/listing can read linked documents
    # or populate a cache through a linked runtime directory.
    for _path in _iter_safe_documents(vault_dir, vault_dir, reject_links=True):
        pass

    docs = list_documents(root_dir, feature=feature)

    if not docs:
        raise VaultSpecError(f"Feature tag '{feature}' matches zero documents.")

    # Find cross-feature links
    cross_links: list[FeatureCrossLink] = []
    try:
        from ..graph import VaultGraph

        graph = VaultGraph(root_dir)
        for doc in docs:
            node = graph.nodes.get(doc.name) or graph.nodes.get(
                f"{doc.doc_type}/{doc.name}"
            )
            if not node:
                continue
            for src_name in node.in_links:
                src_node = graph.nodes.get(src_name)
                if src_node and src_node.feature != feature:
                    cross_links.append(
                        {
                            "source": src_name,
                            "target": node.name,
                            "source_path": str(src_node.path.relative_to(root_dir))
                            if src_node.path
                            else src_name,
                        }
                    )
    except Exception as e:
        logger.warning("Could not analyze cross-feature links: %s", e)

    result = archive_documents(
        root_dir, (doc.path.relative_to(root_dir) for doc in docs), dry_run=dry_run
    )
    archived = [str(path) for path in result.paths]

    return {
        "archived_count": len(archived),
        "paths": archived,
        "cross_links": cross_links,
        "dry_run": dry_run,
    }


def unarchive_feature(
    root_dir: Path, feature: str, dry_run: bool = False
) -> FeatureUnarchiveResult:
    """Move all documents for a feature from ``.vault/_archive/`` back to
    their original locations.

    Args:
        root_dir: Project root directory.
        feature: Feature name to unarchive (leading ``#`` is stripped).
        dry_run: Preview planned changes.

    Returns:
        A :class:`FeatureUnarchiveResult`.
    """
    from ..config import get_config
    from ..core.exceptions import VaultSpecError
    from .models import DocType
    from .parser import parse_frontmatter

    feature = feature.strip().lstrip("#").strip()
    if not feature:
        raise VaultSpecError(
            "A feature tag is required to unarchive.",
        )

    cfg = get_config()
    root_dir = root_dir.resolve()
    vault_dir = root_dir / cfg.docs_dir
    archive_dir = vault_dir / "_archive"
    _require_no_symlink_components(root_dir, vault_dir)
    if not vault_dir.exists():
        raise VaultSpecError(
            f"Feature tag '{feature}' matches zero archived documents."
        )
    _assert_docs_dir(root_dir, vault_dir)
    _assert_runtime_dir(vault_dir)
    _require_no_symlink_components(vault_dir, archive_dir)

    if not archive_dir.exists():
        raise VaultSpecError(
            f"Feature tag '{feature}' matches zero archived documents."
        )

    archived_docs: list[tuple[Path, Path]] = []
    for doc_path in _iter_safe_documents(
        vault_dir, archive_dir, excluded=frozenset({".obsidian"}), reject_links=True
    ):
        try:
            content = read_document_text(doc_path, root_dir=root_dir)
        except (OSError, UnicodeDecodeError):
            continue
        meta, _ = parse_frontmatter(content)
        rel_path = doc_path.relative_to(archive_dir)
        try:
            dt = DocType(rel_path.parts[0])
            dt_str = dt.value
        except (ValueError, KeyError):
            dt_str = "unknown"

        tags = meta.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]

        feature_val = feature_from_tags_or_meta(tags, meta, dt_str)

        if feature_val == feature.lower():
            archived_docs.append((doc_path, rel_path))

    if not archived_docs:
        raise VaultSpecError(
            f"Feature tag '{feature}' matches zero archived documents."
        )

    result = restore_documents(
        root_dir,
        (doc_path.relative_to(root_dir) for doc_path, _rel_path in archived_docs),
        dry_run=dry_run,
    )
    unarchived_paths = [str(path) for path in result.paths]

    if not dry_run:
        _cleanup_empty_dirs(vault_dir, archive_dir)

    return {
        "unarchived_count": len(unarchived_paths),
        "paths": unarchived_paths,
        "dry_run": dry_run,
    }


def _cleanup_empty_dirs(vault_dir: Path, directory: Path) -> None:
    """Recursively delete empty real subdirectories inside the vault."""
    if directory.is_symlink() or directory.is_junction():
        return
    _require_no_symlink_components(vault_dir, directory)
    if not directory.exists() or not directory.is_dir():
        return
    for child in list(directory.iterdir()):
        if child.is_dir() and not (child.is_symlink() or child.is_junction()):
            _cleanup_empty_dirs(vault_dir, child)
    if directory.is_dir() and not list(directory.iterdir()):
        import contextlib

        with contextlib.suppress(OSError):
            directory.rmdir()
