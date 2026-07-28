"""Vault document listing and statistics.

Houses :class:`VaultDocument`, the scan-and-parse helpers that back it, and
the read-only query surface (:func:`list_documents`, :func:`get_stats`,
:func:`list_feature_details`) built on top of them. Split out of
:mod:`.query`, which re-exports everything here for compatibility.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypedDict

from .models import DocType
from .parser import parse_frontmatter
from .scanner import get_doc_type, scan_vault

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from ..graph import VaultGraph

logger = logging.getLogger(__name__)

#: Re-exported for :mod:`vaultspec_core.vaultcore.query` and
#: :mod:`vaultspec_core.vaultcore.query_archive`, which reach into these as
#: the single public import surface for document listing.
__all__ = [
    "docs_from_graph",
    "feature_from_tags_or_meta",
    "scan_all",
]


@dataclass
class VaultDocument:
    """A resolved vault document with parsed metadata.

    Attributes:
        path: Absolute filesystem path to the document.
        name: Filename stem (no extension).
        doc_type: Document type value string (e.g. ``"adr"``, ``"plan"``).
        feature: Feature name extracted from the non-type tag, or ``None``.
        date: ISO 8601 date string from frontmatter or filename, or ``None``.
        tags: Raw tag list from frontmatter.
    """

    path: Path
    name: str
    doc_type: str
    feature: str | None
    date: str | None
    tags: list[str]


def _parse_date_from_filename(name: str) -> str | None:
    """Extract the ``YYYY-MM-DD`` prefix from a vault filename.

    Args:
        name: Filename stem (no directory component).

    Returns:
        Date string such as ``"2026-02-07"``, or ``None`` if absent.
    """
    m = re.match(r"(\d{4}-\d{2}-\d{2})", name)
    return m.group(1) if m else None


def _parse_feature_from_tags(tags: list[str], doc_type_tag: str | None) -> str | None:
    """Return the first non-:class:`~vaultspec_core.vaultcore.models.DocType` tag.

    Args:
        tags: Raw tag list from frontmatter (e.g. ``["#adr", "#editor-demo"]``).
        doc_type_tag: Bare doc-type value to skip (e.g. ``"adr"``), or ``None``.

    Returns:
        Feature name string without the leading ``#``, or ``None`` if not found.
    """
    for tag in tags:
        cleaned = tag.lstrip("#")
        if doc_type_tag and cleaned == doc_type_tag:
            continue
        if cleaned in {dt.value for dt in DocType}:
            continue
        return cleaned
    return None


def feature_from_tags_or_meta(
    tags: list[str], meta: Mapping[str, object], doc_type_tag: str | None
) -> str | None:
    """Derive a document's feature tag, with the bare ``feature:`` fallback.

    Primarily reads *tags* via :func:`_parse_feature_from_tags`, falling
    back to a bare top-level ``feature:`` frontmatter key when no
    tag-derived feature is found. Shared by :func:`scan_all` and
    :func:`docs_from_graph` so both callers apply the identical fallback
    chain against the same parsed frontmatter shape.

    Args:
        tags: Normalised tag list (already coerced from a scalar).
        meta: Parsed frontmatter dict for the document.
        doc_type_tag: Bare doc-type value to skip (e.g. ``"adr"``), or
            ``None``.

    Returns:
        Feature name string without the leading ``#``, or ``None``.
    """
    feature = _parse_feature_from_tags(tags, doc_type_tag)
    if not feature and "feature" in meta:
        feature = str(meta["feature"]).lstrip("#").strip().lower() or None
    return feature


def scan_all(root_dir: Path, *, doc_type: str | None = None) -> list[VaultDocument]:
    """Scan the vault and parse every document into a :class:`VaultDocument`.

    Used internally by :func:`list_documents`, :func:`get_stats`,
    :func:`list_feature_details`, and :mod:`vaultspec_core.vaultcore.checks.features`.

    Args:
        root_dir: Project root directory.
        doc_type: When set, keep only documents of this type.  The type is
            pure path arithmetic (``get_doc_type``), so the filter is
            applied before the file is read: a type-scoped listing reads
            only its own subset of the corpus instead of parsing every
            document and discarding the rest.

    Returns:
        List of :class:`VaultDocument` instances for all readable vault
        files that pass the filter.
    """
    docs: list[VaultDocument] = []
    for doc_path in scan_vault(root_dir):
        dt = get_doc_type(doc_path, root_dir)
        dt_str = dt.value if dt else "unknown"
        if doc_type is not None and dt_str != doc_type:
            continue
        try:
            content = doc_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        meta, _ = parse_frontmatter(content)
        tags = meta.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]
        feature = feature_from_tags_or_meta(tags, meta, dt_str)
        date = meta.get("date") or _parse_date_from_filename(doc_path.name)

        docs.append(
            VaultDocument(
                path=doc_path,
                name=doc_path.stem,
                doc_type=dt_str,
                feature=feature,
                date=str(date) if date else None,
                tags=tags,
            )
        )
    return docs


def docs_from_graph(
    graph: VaultGraph,
    *,
    doc_type: str | None = None,
    feature: str | None = None,
    date: str | None = None,
) -> list[VaultDocument]:
    """Derive :class:`VaultDocument` records from an already-built graph.

    Reuses the frontmatter each node already parsed during the graph build
    instead of re-reading and re-parsing every file from disk, while
    reproducing :func:`scan_all`'s exact field derivation (including the
    bare ``feature:`` fallback and the filename-date fallback) so the
    result is byte-for-byte identical to the uncached path. Phantom nodes
    and ref-scoped nodes (``path is None``) are never part of ``scan_all``'s
    domain and are skipped; a stem-collision node's qualified ``name`` is
    sidestepped by deriving the document name from ``node.path.stem``
    instead.

    Args:
        graph: An already-built :class:`~vaultspec_core.graph.VaultGraph`
            over the same ``root_dir`` the caller would otherwise rescan.
        doc_type: Filter by type, matching :func:`list_documents`'
            concrete-type semantics. The ``"orphaned"``/``"invalid"``
            pseudo-types are not supported here; callers needing them must
            use :func:`list_documents`.
        feature: Filter by feature tag (without ``#`` prefix).
        date: Filter by exact date string (``YYYY-MM-DD``).

    Returns:
        Ordered list of :class:`VaultDocument` instances matching all
        supplied filters.
    """
    # ``scan_all`` drops a document it cannot read or decode, so the graph
    # path must drop it too. The graph still creates a node for such a file
    # (with empty frontmatter and body), which is indistinguishable from a
    # genuinely empty document by its fields alone; the ingress read records
    # the failure separately, and that record is the only sound signal.
    unreadable = {issue.path for issue in graph.encoding_issues}

    docs: list[VaultDocument] = []
    for node in graph.nodes.values():
        if node.phantom or node.path is None or node.path in unreadable:
            continue
        dt_str = node.doc_type.value if node.doc_type else "unknown"
        if doc_type is not None and dt_str != doc_type:
            continue

        meta = node.frontmatter
        tags = meta.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]
        doc_feature = feature_from_tags_or_meta(tags, meta, dt_str)
        doc_date = meta.get("date") or _parse_date_from_filename(node.path.name)

        docs.append(
            VaultDocument(
                path=node.path,
                name=node.path.stem,
                doc_type=dt_str,
                feature=doc_feature,
                date=str(doc_date) if doc_date else None,
                tags=tags,
            )
        )

    if feature:
        feature = feature.lstrip("#")
        docs = [d for d in docs if d.feature == feature]

    if date:
        docs = [d for d in docs if d.date == date]

    return docs


def list_documents(
    root_dir: Path,
    *,
    doc_type: str | None = None,
    feature: str | None = None,
    date: str | None = None,
    graph: VaultGraph | None = None,
) -> list[VaultDocument]:
    """List vault documents with optional filters.

    Args:
        root_dir: Project root directory.
        doc_type: Filter by type. Standard types: ``adr``, ``audit``,
            ``exec``, ``plan``, ``reference``, ``research``. Special
            values: ``"orphaned"`` (no incoming links), ``"invalid"``
            (contains dangling outgoing links).
        feature: Filter by feature tag (without ``#`` prefix).
        date: Filter by exact date string (``YYYY-MM-DD``).
        graph: Optional pre-built :class:`~vaultspec_core.graph.VaultGraph`
            to reuse. One is built when omitted, and the already-parsed
            frontmatter it carries backs the listing instead of a second
            read-and-parse of every document. A graph that cannot be built
            degrades to the direct disk scan rather than failing.

    Returns:
        Ordered list of :class:`VaultDocument` instances matching all
        supplied filters.
    """
    if graph is None:
        try:
            from ..graph import VaultGraph as _VaultGraph

            graph = _VaultGraph(root_dir)
        except (OSError, ValueError) as exc:
            logger.warning("Failed to build vault graph for listing: %s", exc)
            graph = None

    if graph is not None:
        # The pseudo-types are graph predicates over the same derived set, so
        # they filter the graph-backed listing rather than triggering a second
        # full scan alongside the graph they already needed.
        docs = docs_from_graph(
            graph, doc_type=None if doc_type in ("orphaned", "invalid") else doc_type
        )
        if doc_type == "orphaned":
            orphan_names = set(graph.get_orphaned())
            docs = [d for d in docs if d.name in orphan_names]
        elif doc_type == "invalid":
            dangling_sources = {src for src, _ in graph.get_dangling_links()}
            docs = [d for d in docs if d.name in dangling_sources]
    elif doc_type in ("orphaned", "invalid"):
        # Both pseudo-types are defined by graph edges; without a graph there
        # is no sound answer, so report nothing rather than something wrong.
        docs = []
    else:
        # A concrete doc-type filter is path-derived and applied inside the
        # scan, before any file is read.
        docs = scan_all(root_dir, doc_type=doc_type)

    if feature:
        feature = feature.lstrip("#")
        docs = [d for d in docs if d.feature == feature]

    if date:
        docs = [d for d in docs if d.date == date]

    return docs


class VaultStats(TypedDict):
    """Aggregate counts returned by :func:`get_stats`."""

    total_docs: int
    total_features: int
    counts_by_type: dict[str, int]
    orphaned_count: int
    dangling_link_count: int


def get_stats(
    root_dir: Path,
    *,
    feature: str | None = None,
    doc_type: str | None = None,
    date: str | None = None,
    graph: VaultGraph | None = None,
) -> VaultStats:
    """Compute vault statistics with optional filters.

    Args:
        root_dir: Project root directory.
        feature: Restrict counts to a single feature (without ``#``).
        doc_type: Restrict counts to a single document type.
        date: Restrict to documents matching this date (``YYYY-MM-DD``).
        graph: Optional pre-built :class:`~vaultspec_core.graph.VaultGraph`
            to reuse. When *doc_type* is not the ``"orphaned"``/``"invalid"``
            pseudo-type, the graph's already-parsed frontmatter also backs
            the document listing (via :func:`docs_from_graph`) instead of
            a fresh disk scan; callers that already hold a graph (the
            orientation rollup) pass it so the stats path never rebuilds
            or rescans the corpus a second time.

    Returns:
        Dict with keys: ``total_docs``, ``total_features``,
        ``counts_by_type`` (``dict[str, int]``), ``orphaned_count``,
        ``dangling_link_count``. Orphan and invalid counts are always
        computed against the full unfiltered vault via
        :class:`~vaultspec_core.graph.VaultGraph`.
    """
    if graph is None:
        try:
            from ..graph import VaultGraph as _VaultGraph

            graph = _VaultGraph(root_dir)
        except (OSError, ValueError) as exc:
            logger.warning("Failed to build vault graph for stats: %s", exc)
            graph = None

    # The "orphaned"/"invalid" pseudo-types need list_documents' own
    # graph-backed semantics; every concrete type (and the unfiltered case)
    # reads from the already-built graph instead of rescanning the corpus.
    if graph is not None and doc_type not in ("orphaned", "invalid"):
        docs = docs_from_graph(graph, feature=feature, doc_type=doc_type, date=date)
    else:
        docs = list_documents(root_dir, feature=feature, doc_type=doc_type, date=date)

    counts_by_type: dict[str, int] = {}
    features: set[str] = set()
    for d in docs:
        counts_by_type[d.doc_type] = counts_by_type.get(d.doc_type, 0) + 1
        if d.feature:
            features.add(d.feature)

    orphaned_count = 0
    dangling_link_count = 0
    if graph is not None:
        try:
            orphaned_count = len(graph.get_orphaned())
            dangling_link_count = len(graph.get_dangling_links())
        except (OSError, ValueError) as exc:
            logger.warning("Failed to compute orphan/dangling counts: %s", exc)

    return {
        "total_docs": len(docs),
        "total_features": len(features),
        "counts_by_type": counts_by_type,
        "orphaned_count": orphaned_count,
        "dangling_link_count": dangling_link_count,
    }


class FeatureDetail(TypedDict):
    """Enriched per-feature metadata row returned by :func:`list_feature_details`."""

    name: str
    doc_count: int
    types: list[str]
    earliest_date: str | None
    latest_activity: str | None
    has_plan: bool


def list_feature_details(
    root_dir: Path,
    *,
    date: str | None = None,
    doc_type: str | None = None,
    orphaned_only: bool = False,
) -> list[FeatureDetail]:
    """List features with enriched per-feature metadata.

    Args:
        root_dir: Project root directory.
        date: Exclude features whose earliest document date is after this
            value (``YYYY-MM-DD``).
        doc_type: Restrict to features that contain at least one document
            of this type.
        orphaned_only: When ``True``, return only features where every
            document is orphaned (no incoming wiki-links).

    Returns:
        List of :class:`FeatureDetail` rows sorted by feature name.
    """
    docs = scan_all(root_dir)

    # Group by feature
    by_feature: dict[str, list[VaultDocument]] = {}
    for d in docs:
        if d.feature:
            by_feature.setdefault(d.feature, []).append(d)

    # Orphan detection
    orphan_features: set[str] = set()
    if orphaned_only:
        from ..graph import VaultGraph

        graph = VaultGraph(root_dir)
        orphan_names = set(graph.get_orphaned())
        for feat, feat_docs in by_feature.items():
            if all(d.name in orphan_names for d in feat_docs):
                orphan_features.add(feat)

    results: list[FeatureDetail] = []
    for feat, feat_docs in sorted(by_feature.items()):
        if orphaned_only and feat not in orphan_features:
            continue

        types = {d.doc_type for d in feat_docs}

        if doc_type and doc_type not in types:
            continue

        dates = [d.date for d in feat_docs if d.date]
        earliest = min(dates) if dates else None
        latest = max(dates) if dates else None

        if date and earliest and earliest > date:
            continue

        results.append(
            {
                "name": feat,
                "doc_count": len(feat_docs),
                "types": sorted(types),
                "earliest_date": earliest,
                "latest_activity": latest,
                "has_plan": "plan" in types,
            }
        )

    return results
