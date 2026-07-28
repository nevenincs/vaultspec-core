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
module re-exports the public surface of each sibling module, so no import
site outside this package needs to change. Helpers that stay private to
their defining module (never imported by another module or a test) are not
re-exported here.
"""

from __future__ import annotations

from .query_archive import (
    FeatureArchiveResult,
    FeatureCrossLink,
    FeatureUnarchiveResult,
    archive_feature,
    unarchive_feature,
)
from .query_listing import (
    FeatureDetail,
    VaultDocument,
    docs_from_graph,
    feature_from_tags_or_meta,
    get_stats,
    list_documents,
    list_feature_details,
    logger,
    scan_all,
)
from .query_rename import (
    RenameCollision,
    RenamePlan,
    analyze_cross_feature_links,
    assert_within_docs,
    compute_rename_plan,
    predict_rewrites,
    rel,
    rewrite_feature_tag_block,
    validate_feature_rename,
)
from .query_rename_apply import (
    FeatureRenameResult,
    RenameApplyResult,
    RenameIndexInfo,
    RenameLinkPair,
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
    "RenamePlan",
    "VaultDocument",
    "analyze_cross_feature_links",
    "archive_feature",
    "assert_within_docs",
    "compute_rename_plan",
    "docs_from_graph",
    "feature_from_tags_or_meta",
    "get_stats",
    "list_documents",
    "list_feature_details",
    "logger",
    "predict_rewrites",
    "rel",
    "rename_feature",
    "rewrite_feature_tag_block",
    "scan_all",
    "unarchive_feature",
    "validate_feature_rename",
]
