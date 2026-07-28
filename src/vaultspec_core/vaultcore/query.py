"""Unified query engine for .vault/ document operations.

Composes :mod:`.scanner` and :mod:`.parser` into a single query surface
used by CLI commands (``vaultspec-core vault stats``,
``vaultspec-core vault list``, ``vaultspec-core vault feature list``).
Exports :class:`VaultDocument`, :func:`list_documents`, :func:`get_stats`,
:func:`list_feature_details`, :func:`archive_feature`, and
:func:`rename_feature`.

This module is the public surface for the vault query engine: the actual
implementations live in sibling modules, split along natural seams
(:mod:`.query_listing` for the read-only document listing/stats surface,
:mod:`.query_archive` for feature archive/unarchive, and
:mod:`.query_rename` + :mod:`.query_rename_apply` for the two halves of
feature rename - plan computation and transactional apply). Importing this
module re-exports the full prior public surface, including the
underscore-prefixed helpers other modules and tests import directly, so no
import site outside this package needs to change.
"""

from __future__ import annotations

from .query_archive import (
    FeatureArchiveResult,
    FeatureCrossLink,
    FeatureUnarchiveResult,
    _cleanup_empty_dirs,
    archive_feature,
    unarchive_feature,
)
from .query_listing import (
    FeatureDetail,
    VaultDocument,
    _docs_from_graph,
    _feature_from_tags_or_meta,
    _parse_date_from_filename,
    _parse_feature_from_tags,
    _scan_all,
    get_stats,
    list_documents,
    list_feature_details,
    logger,
)
from .query_rename import (
    RenameCollision,
    _analyze_cross_feature_links,
    _assert_within_docs,
    _compute_rename_plan,
    _count_related_refs,
    _match_exec_folder_date,
    _parse_inline_tags,
    _predict_rewrites,
    _rel,
    _RenamePlan,
    _rewrite_feature_tag_block,
    _same_file,
    _swap_authored_filename,
    _swap_exec_filename,
    _validate_feature_rename,
)
from .query_rename_apply import (
    FeatureRenameResult,
    RenameApplyResult,
    RenameIndexInfo,
    RenameLinkPair,
    _apply_rename_plan,
    _refresh_rename_stamps,
    _regenerate_feature_index,
    rename_feature,
)

__all__ = [
    "FeatureArchiveResult",
    "FeatureCrossLink",
    "FeatureDetail",
    "FeatureRenameResult",
    "FeatureUnarchiveResult",
    "RenameApplyResult",
    "RenameCollision",
    "RenameIndexInfo",
    "RenameLinkPair",
    "VaultDocument",
    "_RenamePlan",
    "_analyze_cross_feature_links",
    "_apply_rename_plan",
    "_assert_within_docs",
    "_cleanup_empty_dirs",
    "_compute_rename_plan",
    "_count_related_refs",
    "_docs_from_graph",
    "_feature_from_tags_or_meta",
    "_match_exec_folder_date",
    "_parse_date_from_filename",
    "_parse_feature_from_tags",
    "_parse_inline_tags",
    "_predict_rewrites",
    "_refresh_rename_stamps",
    "_regenerate_feature_index",
    "_rel",
    "_rewrite_feature_tag_block",
    "_same_file",
    "_scan_all",
    "_swap_authored_filename",
    "_swap_exec_filename",
    "_validate_feature_rename",
    "archive_feature",
    "get_stats",
    "list_documents",
    "list_feature_details",
    "logger",
    "rename_feature",
    "unarchive_feature",
]
