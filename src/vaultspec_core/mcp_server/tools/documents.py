"""Document-domain MCP tools: batch ``create`` and batch ``edit``.

Both tools are batch-native and route every mutation through the shared
``vaultcore`` cores - no creation, filename, or edit logic is authored in
this layer.  ``create`` is a thin sequential loop over
:func:`~vaultspec_core.vaultcore.hydration.create_vault_doc` plus a
side-effect regeneration of each affected feature index via
:func:`~vaultspec_core.vaultcore.index.generate_feature_index`; ``edit``
composes a full body from section-addressed operations and flows it through
:func:`~vaultspec_core.vaultcore.edit_engine.execute_edit`, inheriting its
optimistic-concurrency guard, pre-write conformance checks, and post-write
blob hash.  Both surface the unified per-item envelope from
:mod:`vaultspec_core.mcp_server.results`; whole-call failures (an empty
batch) raise to the protocol ``isError`` layer.
"""

from __future__ import annotations

import datetime
import logging
import re
from typing import TYPE_CHECKING, Any

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from ...core.types import get_context as _get_ctx
from ...vaultcore.models import DocType
from ..isolation import isolated_context as _isolated_context
from ..results import BatchResult, ItemResult, build_batch, build_item

if TYPE_CHECKING:
    from pathlib import Path

    from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

__all__ = ["register_document_tools"]


# ---------------------------------------------------------------------------
# find: document discovery and feature listing
# ---------------------------------------------------------------------------

#: The default document-search types when the caller supplies no ``type``
#: filter; exec and audit are excluded unless explicitly requested.
_DEFAULT_TYPES = ["adr", "plan", "research", "reference"]


class FindEntry(BaseModel):
    """One ``find`` result row, covering both find modes as a superset.

    Feature-listing mode populates the feature fields (``doc_count`` /
    ``weight`` / ``status`` / ``types`` / ``earliest_date`` / ``has_plan``);
    document-search mode populates the document fields (``type`` /
    ``feature`` / ``date`` / ``path`` / ``blob_hash`` / ``resource_uri`` and
    the optional inline ``body``). ``name`` is always present. A single
    superset model lets ``find`` declare one ``outputSchema`` while keeping
    the flat-list return shape both modes have always had.

    Attributes:
        name: Feature name (listing mode) or document stem (search mode).
        doc_count: Document count for the feature (listing mode).
        weight: Graph-weight ranking score for the feature (listing mode).
        status: Lifecycle status sourced from
            :func:`~vaultspec_core.vaultcore.orientation.feature_lifecycle_status`
            (listing mode, ``json`` only).
        types: The document-type values present for the feature (listing
            mode, ``json`` only).
        earliest_date: The feature's earliest document date (listing mode,
            ``json`` only).
        has_plan: Whether the feature has a plan (listing mode, ``json``
            only).
        note: An advisory note (e.g. graph ranking unavailable).
        type: The document type value (search mode).
        feature: The document's feature tag without ``#`` (search mode).
        date: The document's date string (search mode).
        path: The document path relative to the project root (search mode).
        blob_hash: The git blob OID of the document's current bytes, so a
            read-then-edit chain avoids a re-read (search mode).
        resource_uri: A ``file://`` resource-link URI for the document body,
            the ``resource_link``-style return with inline ``body`` as the
            fallback (search mode).
        body: The full document text, present only when ``body=True`` was
            requested (search mode).
    """

    name: str
    # Feature-listing mode.
    doc_count: int | None = None
    weight: int | None = None
    status: str | None = None
    types: list[str] | None = None
    earliest_date: str | None = None
    has_plan: bool | None = None
    note: str | None = None
    # Document-search mode.
    type: str | None = None
    feature: str | None = None
    date: str | None = None
    path: str | None = None
    blob_hash: str | None = None
    resource_uri: str | None = None
    body: str | None = None


# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------


class DocumentSpec(BaseModel):
    """One document to scaffold in a batch ``create`` call.

    Attributes:
        feature: The feature handle (kebab-case; a leading ``#`` is stripped
            and the token is validated by the shared normalizer).
        type: The document type (``research`` / ``adr`` / ``plan`` /
            ``reference`` / ``audit`` / ``exec``); defaults to ``research``.
            ``index`` is rejected - indexes are auto-generated.
        title: Optional document title, rendered into the heading.
        date: Optional ISO-8601 date; defaults to today (UTC).
        content: Optional seed prose appended as a ``## Context`` section
            after scaffolding, routed through the shared edit engine.
        related: Optional references (path, stem, filename, or wiki-link)
            resolved to ``[[wiki-link]]`` entries in ``related:``.
        tags: Optional additional ``#tag`` strings beyond the required
            directory and feature tags.
        tier: The plan tier (``L1``-``L4``) for a ``plan`` document; defaults
            to ``L1``. Ignored for other document types.
        topic: Optional kebab-case narrative filename infix disambiguating a
            second document of the same type for a feature
            (``{date}-{feature}-{topic}-{type}.md``). Only valid for
            ``audit``, ``reference``, and ``research`` documents.
    """

    feature: str
    type: str | None = None
    title: str | None = None
    date: str | None = None
    content: str | None = None
    related: list[str] | None = None
    tags: list[str] | None = None
    tier: str | None = None
    topic: str | None = None


class EditOperation(BaseModel):
    """One body-prose operation in a batch ``edit`` call.

    Attributes:
        target: The document address - a stem, filename, path, or
            ``[[wiki-link]]``.
        operation: The edit verb - ``append_section`` (append prose to an
            existing section), ``replace_section`` (replace an existing
            section's prose), or ``set_body`` (replace the whole body).
        content: The prose to apply (a full body for ``set_body``, a
            section's prose otherwise).
        section: The exact heading-line text (e.g. ``## Context``) addressing
            the section for ``append_section`` / ``replace_section``;
            unused for ``set_body``.
        expected_blob_hash: Optional optimistic-concurrency guard - the git
            blob OID the caller believes is current; a mismatch fails the
            item as a ``conflict`` without writing.
    """

    target: str
    operation: str
    content: str
    section: str | None = None
    expected_blob_hash: str | None = Field(default=None)


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


def _create_one(
    root_dir: Path,
    index: int,
    spec: DocumentSpec,
    today: str,
) -> tuple[ItemResult, str | None]:
    """Scaffold one document, returning its item result and affected feature.

    Every failure path is folded into a ``failed`` :class:`ItemResult`; the
    second tuple element is the normalized feature name on success (for the
    end-of-batch index regeneration) or ``None`` on failure.

    Args:
        root_dir: The project root whose ``.vault/`` receives the document.
        index: The item's zero-based batch position.
        spec: The document specification.
        today: The default ISO date used when the spec omits one.

    Returns:
        A two-tuple ``(item_result, affected_feature_or_None)``.
    """
    from ...vaultcore.hydration import create_vault_doc
    from ...vaultcore.normalize import normalize_feature_tag
    from ...vaultcore.resolve import (
        RelatedResolutionError,
        resolve_related_inputs,
        validate_feature_dependencies,
    )

    type_str = spec.type or "research"
    target = f"{type_str}:{spec.feature}"

    def _failed(message: str, **extra: Any) -> tuple[ItemResult, None]:
        return (
            build_item(
                index,
                status="failed",
                target=target,
                error={"message": message, **extra},
            ),
            None,
        )

    norm = normalize_feature_tag(spec.feature)
    if not norm.ok or norm.value is None:
        return _failed(norm.error or "invalid feature")
    feature = norm.value

    try:
        doc_type = DocType(type_str)
    except ValueError:
        return _failed(f"Invalid document type: {type_str}")
    if doc_type is DocType.INDEX:
        return _failed(
            "'index' documents are auto-generated. "
            "Use 'vaultspec-core vault feature index', not create."
        )

    extra_tags: list[str] | None = None
    if spec.tags:
        extra_tags = []
        for tag in spec.tags:
            tag_norm = normalize_feature_tag(tag, label="tag")
            if not tag_norm.ok or tag_norm.value is None:
                return _failed(tag_norm.error or "invalid tag")
            extra_tags.append(f"#{tag_norm.value}")

    resolved_related: list[str] | None = None
    if spec.related:
        try:
            resolved_related = resolve_related_inputs(spec.related, root_dir)
        except RelatedResolutionError as exc:
            return _failed(
                "Cannot resolve related document(s): " + "; ".join(exc.failures),
                failures=exc.failures,
            )

    # Lifecycle-dependency validation runs against the on-disk vault, which
    # already includes any earlier same-batch items - they were written
    # sequentially before this one - so an intra-batch dependency (create the
    # ADR then the plan in one call) is satisfied without special tracking.
    warnings: list[str] = []
    for diag in validate_feature_dependencies(root_dir, doc_type, feature):
        if diag.startswith("ERROR:"):
            return _failed(diag)
        if diag.startswith("WARNING:"):
            warnings.append(diag)

    tier: str | None = None
    if doc_type is DocType.PLAN:
        tier = spec.tier or "L1"
        if tier not in ("L1", "L2", "L3", "L4"):
            return _failed(f"Invalid tier '{tier}'. Allowed values: L1, L2, L3, L4.")

    topic: str | None = None
    if spec.topic is not None:
        if doc_type not in (DocType.AUDIT, DocType.REFERENCE, DocType.RESEARCH):
            return _failed(
                "topic is only valid for 'audit', 'reference', and "
                "'research' documents."
            )
        topic_norm = normalize_feature_tag(spec.topic, label="topic")
        if not topic_norm.ok or topic_norm.value is None:
            return _failed(topic_norm.error or "invalid topic")
        topic = topic_norm.value

    date_str = spec.date or today
    try:
        created = create_vault_doc(
            root_dir,
            doc_type,
            feature,
            date_str,
            spec.title,
            topic=topic,
            related=resolved_related,
            extra_tags=extra_tags,
            tier=tier,
        )
    except FileNotFoundError as exc:
        return _failed(f"Template unavailable: {exc}")
    except Exception as exc:  # ResourceExistsError, scaffold-validation, write
        return _failed(str(exc))

    seed_warnings = _apply_seed_content(root_dir, created, spec.content)
    warnings.extend(seed_warnings)

    from ...vaultcore.blob_hash import git_blob_oid

    item = build_item(
        index,
        status="created",
        target=target,
        path=str(created.relative_to(root_dir)),
        blob_hash=git_blob_oid(created.read_bytes()),
        warnings=warnings,
    )
    return item, feature


def _apply_seed_content(
    root_dir: Path,
    doc_path: Path,
    content: str | None,
) -> list[str]:
    """Append optional seed prose to a freshly-scaffolded document.

    The append is routed through the shared edit engine (a full-body
    recompose plus write), so seed content obeys the same conformance
    checks and ``modified:`` stamp refresh as any other body edit and no
    write logic is authored here.  A failed append degrades to a warning:
    the document was still created.

    Args:
        root_dir: The project root.
        doc_path: The just-created document.
        content: The seed prose, or ``None`` to skip.

    Returns:
        Advisory messages (empty when there was nothing to append or the
        append succeeded).
    """
    if not content:
        return []

    from ...vaultcore.edit_engine import execute_edit

    _frontmatter, body = _split_body(doc_path.read_text(encoding="utf-8"))
    new_body = body.rstrip("\n") + "\n\n## Context\n\n" + content.strip("\n") + "\n"
    result = execute_edit(root_dir, ref=str(doc_path), new_body=new_body)
    if result.status == "failed":
        message = "unknown error"
        if result.error is not None:
            message = str(result.error.get("message", message))
        return [f"Seed content not applied: {message}"]
    return []


# ---------------------------------------------------------------------------
# edit: section addressing and body composition
# ---------------------------------------------------------------------------


_FRONTMATTER_RE = re.compile(r"^(﻿?---[ \t]*\n.*?\n---[ \t]*\n?)(.*)$", re.DOTALL)
_HEADING_RE = re.compile(r"^(#{1,6})\s")


def _split_body(text: str) -> tuple[str, str]:
    """Split full document text into ``(frontmatter_block, body)``.

    The frontmatter block keeps its fences and trailing newline, so the body
    is exactly the bytes after the frontmatter - the portion the edit engine
    replaces.  A document with no frontmatter yields ``("", text)``.

    Args:
        text: Full document text (LF line endings).

    Returns:
        A two-tuple ``(frontmatter_block, body)``.
    """
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return "", text
    return match.group(1), match.group(2)


def _heading_level(line: str) -> int | None:
    """Return the ATX heading level of *line*, or ``None`` if not a heading.

    Args:
        line: A single body line.

    Returns:
        The number of leading ``#`` (1-6) for a heading line; ``None``
        otherwise.
    """
    match = _HEADING_RE.match(line)
    return len(match.group(1)) if match else None


def _locate_section(lines: list[str], heading: str) -> tuple[int, int] | None:
    """Locate a section by exact heading-line text (first match).

    The section spans from its heading line through to the next heading of
    the same or a higher level (fewer or equal ``#``), or end of body.

    Args:
        lines: The body split on ``\\n``.
        heading: The exact heading-line text to match (whitespace-trimmed).

    Returns:
        A ``(heading_index, section_end_index)`` half-open line range, or
        ``None`` when no line matches the heading text.
    """
    wanted = heading.strip()
    for i, line in enumerate(lines):
        if line.strip() != wanted:
            continue
        level = _heading_level(line)
        end = len(lines)
        for k in range(i + 1, len(lines)):
            klevel = _heading_level(lines[k])
            if klevel is not None and level is not None and klevel <= level:
                end = k
                break
        return i, end
    return None


def _compose_body(op: EditOperation, body: str) -> str | None:
    """Compose the new full body for one edit operation.

    Args:
        op: The edit operation (its ``operation``, ``section``, ``content``).
        body: The current document body (bytes after the frontmatter, LF).

    Returns:
        The composed new body, or ``None`` when a section op addressed a
        heading that does not exist (the caller reports ``section_not_found``).
    """
    content = op.content.replace("\r\n", "\n").replace("\r", "\n")

    if op.operation == "set_body":
        return "\n" + content.strip("\n") + "\n"

    lines = body.split("\n")
    located = _locate_section(lines, op.section or "")
    if located is None:
        return None
    start, end = located
    content_lines = content.split("\n")

    if op.operation == "append_section":
        head = lines[:end]
        while head and head[-1].strip() == "":
            head.pop()
        new_lines = [*head, "", *content_lines, "", *lines[end:]]
    else:  # replace_section: keep the heading line, replace its prose
        new_lines = [*lines[: start + 1], "", *content_lines, "", *lines[end:]]

    return "\n".join(new_lines)


def _edit_one(root_dir: Path, index: int, op: EditOperation) -> ItemResult:
    """Apply one edit operation, returning its per-item result.

    Resolves the target, composes the new body for the section op, and
    routes the write through :func:`execute_edit` so the concurrency guard,
    conformance checks, and post-write blob hash all apply uniformly.

    Args:
        root_dir: The project root.
        index: The item's zero-based batch position.
        op: The edit operation.

    Returns:
        The per-item :class:`ItemResult`.
    """
    from ...vaultcore.edit_engine import execute_edit

    if op.operation not in ("append_section", "replace_section", "set_body"):
        return build_item(
            index,
            status="failed",
            target=op.target,
            error={"message": f"Unknown edit operation: {op.operation}"},
        )
    if op.operation in ("append_section", "replace_section") and not op.section:
        return build_item(
            index,
            status="failed",
            target=op.target,
            error={"message": f"'{op.operation}' requires a section heading"},
        )

    doc_path = _resolve_target(root_dir, op.target)
    if doc_path is None:
        return build_item(
            index,
            status="failed",
            target=op.target,
            error={"message": f"Cannot resolve document: '{op.target}'"},
        )

    _frontmatter, body = _split_body(doc_path.read_text(encoding="utf-8"))
    new_body = _compose_body(op, body)
    if new_body is None:
        return build_item(
            index,
            status="failed",
            target=op.target,
            path=str(doc_path.relative_to(root_dir)),
            error={
                "message": f"Section not found: '{op.section}'",
                "section_not_found": True,
                "section": op.section,
            },
        )

    result = execute_edit(
        root_dir,
        ref=str(doc_path),
        new_body=new_body,
        expected_blob_hash=op.expected_blob_hash,
    )
    return _edit_result_to_item(root_dir, index, op.target, result)


def _resolve_target(root_dir: Path, ref: str) -> Path | None:
    """Resolve an edit target to its backing document path.

    Uses the same reference resolution as the edit engine
    (:func:`resolve_related_inputs` then a stem-to-path scan) so the tool
    and the CLI agree on what a stem or path addresses.

    Args:
        root_dir: The project root.
        ref: A stem, filename, path, or ``[[wiki-link]]``.

    Returns:
        The absolute backing path, or ``None`` when unresolvable.
    """
    from ...vaultcore.resolve import RelatedResolutionError, resolve_related_inputs
    from ...vaultcore.scanner import scan_vault

    try:
        resolved = resolve_related_inputs([ref], root_dir)
    except RelatedResolutionError:
        return None
    if not resolved:
        return None
    stem = resolved[0][2:-2]
    for doc_path in scan_vault(root_dir):
        if doc_path.stem == stem:
            return doc_path
    return None


def _edit_result_to_item(
    root_dir: Path,
    index: int,
    target: str,
    result: Any,
) -> ItemResult:
    """Map an :class:`EditResult` onto the shared per-item envelope.

    Args:
        root_dir: The project root (to relativise the path).
        index: The item's zero-based batch position.
        target: The submitted target address, echoed back.
        result: The :class:`~vaultspec_core.vaultcore.edit_engine.EditResult`.

    Returns:
        The per-item :class:`ItemResult`.
    """
    from pathlib import Path as _Path

    rel_path: str | None = None
    if result.path is not None:
        try:
            rel_path = str(_Path(result.path).relative_to(root_dir))
        except ValueError:
            rel_path = result.path

    return build_item(
        index,
        status=result.status,
        target=target,
        path=rel_path,
        blob_hash=result.blob_hash,
        error=result.error,
        warnings=result.warnings,
    )


def _regenerate_indexes(root_dir: Path, features: set[str]) -> None:
    """Regenerate the feature index for every feature touched by a batch.

    The graph is built with the cache bypassed so the freshly-written
    documents are seen; index generation is the automatic side effect the
    ADR folds into ``create``, absorbing the manual ``vault feature index``
    call class.

    Args:
        root_dir: The project root.
        features: The normalized feature names to regenerate indexes for.
    """
    from ...graph import VaultGraph
    from ...vaultcore.index import generate_feature_index

    graph = VaultGraph(root_dir, use_cache=False)
    for feature in sorted(features):
        nodes = graph.get_feature_nodes(feature)
        if nodes:
            generate_feature_index(root_dir, feature, nodes=nodes)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def _find_features(limit: int, want_json: bool) -> list[FindEntry]:
    """Build the feature-listing ``find`` result rows.

    The lifecycle ``status`` is sourced from the orientation core
    (:func:`~vaultspec_core.vaultcore.orientation.feature_lifecycle_status`
    over :func:`~vaultspec_core.vaultcore.orientation.compute_rollup`), never
    a local inference, so the MCP surface and ``vaultspec-core status`` agree.

    Args:
        limit: Maximum number of features to return.
        want_json: When ``True``, enrich each row with lifecycle status,
            types, earliest date, and the plan flag.

    Returns:
        The feature-listing rows, ordered as
        :func:`~vaultspec_core.vaultcore.query.list_feature_details` returns
        them and capped at *limit*.
    """
    from ...graph import VaultGraph
    from ...vaultcore.orientation import compute_rollup, feature_lifecycle_status
    from ...vaultcore.query import list_feature_details

    root_dir = _get_ctx().target_dir
    features = list_feature_details(root_dir)

    graph_unavailable = False
    try:
        graph = VaultGraph(root_dir)
        rankings = dict(graph.get_feature_rankings(limit=100))
    except (OSError, ValueError) as exc:
        logger.warning("Failed to load vault graph rankings: %s", exc)
        rankings = {}
        graph_unavailable = True

    active_by_name: dict[str, Any] = {}
    if want_json:
        # The orientation rollup is only needed for the enriched lifecycle
        # status; the cheap listing path skips building the graph twice.
        rollup = compute_rollup(
            root_dir, graph=graph if not graph_unavailable else None
        )
        active_by_name = {f.name: f for f in rollup.active_features}

    rows: list[FindEntry] = []
    for feat in features[:limit]:
        entry = FindEntry(
            name=feat["name"],
            doc_count=feat["doc_count"],
            weight=rankings.get(feat["name"], 0),
            note="graph ranking unavailable" if graph_unavailable else None,
        )
        if want_json:
            active = active_by_name.get(feat["name"])
            entry.status = (
                feature_lifecycle_status(active, set(feat["types"]))
                if active is not None
                else "Unknown"
            )
            entry.types = feat["types"]
            entry.earliest_date = feat["earliest_date"]
            entry.has_plan = feat["has_plan"]
        rows.append(entry)
    return rows


def _find_documents(
    feature: str | None,
    types: list[str] | None,
    date: str | None,
    body: bool,
    limit: int,
) -> list[FindEntry]:
    """Build the document-search ``find`` result rows.

    Each row carries the document's current ``blob_hash`` (so a
    read-then-edit chain avoids a re-read) and a ``resource_uri``
    resource-link, with the full ``body`` inlined only when requested.

    The types are searched in the order given (or the default order) and
    ``limit`` is a single *global* cap applied to the concatenated result, not
    a per-type quota: an early type that fills the cap can crowd out later
    types, so a caller who needs a fair spread across types should page by
    calling once per type.

    Args:
        feature: Feature filter without ``#``, or ``None``.
        types: Document-type filter, or ``None`` for the default set.
        date: Exact-date filter, or ``None``.
        body: When ``True``, inline the full document text.
        limit: Maximum number of documents to return across all types combined.

    Returns:
        The document rows, ordered by the type list and capped globally at
        *limit*.
    """
    from ...vaultcore.blob_hash import git_blob_oid
    from ...vaultcore.query import list_documents

    root_dir = _get_ctx().target_dir
    effective_types = types if types else _DEFAULT_TYPES

    all_docs = []
    for dt in effective_types:
        all_docs.extend(
            list_documents(root_dir, doc_type=dt, feature=feature, date=date)
        )

    rows: list[FindEntry] = []
    for doc in all_docs[:limit]:
        raw: bytes | None = None
        try:
            raw = doc.path.read_bytes()
        except OSError:
            logger.warning("Failed to read %s for blob hash", doc.name)
        entry = FindEntry(
            name=doc.name,
            type=doc.doc_type,
            feature=doc.feature,
            date=doc.date,
            path=str(doc.path.relative_to(root_dir)),
            blob_hash=git_blob_oid(raw) if raw is not None else None,
            resource_uri=doc.path.as_uri(),
        )
        if body:
            entry.body = (
                raw.decode("utf-8", errors="replace") if raw is not None else ""
            )
        rows.append(entry)
    return rows


def register_document_tools(mcp: FastMCP) -> None:
    """Register the ``find``, ``create``, and ``edit`` document tools on *mcp*.

    ``find`` is read-only and idempotent; ``create`` is non-read-only,
    non-destructive, and non-idempotent (recreating an existing document
    fails); ``edit`` is non-read-only, destructive (``set_body`` /
    ``replace_section`` overwrite prose), and non-idempotent.  ``create`` and
    ``edit`` declare their structured output through the
    :class:`~vaultspec_core.mcp_server.results.BatchResult` return type;
    ``find`` declares its output through the :class:`FindEntry` list return.

    Args:
        mcp: The :class:`~mcp.server.fastmcp.FastMCP` instance to decorate.
    """

    @mcp.tool(
        annotations=ToolAnnotations(
            readOnlyHint=True,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    @_isolated_context
    async def find(
        ctx: Context,
        feature: str | None = None,
        type: list[str] | None = None,
        date: str | None = None,
        body: bool = False,
        json: bool = False,
        limit: int = 20,
    ) -> list[FindEntry]:
        """Find vault documents or list features.

        With no filters, returns every feature with its document count and
        graph-weight score; add ``json`` for the orientation-sourced
        lifecycle status and richer metadata.  With any of ``feature`` /
        ``type`` / ``date``, switches to document search: each result carries
        the document's current ``blob_hash`` and a ``resource_uri``
        resource-link, with the full ``body`` inlined only on request.  The
        ``type`` filter defaults to adr, plan, research, reference; exec and
        audit are excluded unless explicitly requested.

        Args:
            ctx: The MCP request context.
            feature: Feature filter without ``#`` (switches to search mode).
            type: Document-type filter (switches to search mode).
            date: Exact-date filter (switches to search mode).
            body: Inline the full document text in search mode.
            json: Enrich the feature listing with lifecycle status.
            limit: Maximum number of rows to return. In search mode this is a
                global cap across all requested types in type-list order, not
                a per-type quota.

        Returns:
            The result rows, one :class:`FindEntry` each.
        """
        await ctx.info(
            f"find: feature={feature!r} type={type!r} date={date!r} "
            f"body={body} json={json} limit={limit}"
        )

        if not feature and not type and not date:
            rows = _find_features(limit, json)
            await ctx.debug(f"Listed {len(rows)} features.")
            return rows

        rows = _find_documents(feature, type, date, body, limit)
        await ctx.debug(f"Found {len(rows)} documents.")
        return rows

    @mcp.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    @_isolated_context
    async def create(ctx: Context, documents: list[DocumentSpec]) -> BatchResult:
        """Scaffold one or more vault documents from templates.

        Each spec is normalized, its related references resolved, and its
        feature lifecycle validated (against the vault including earlier
        same-batch items) before scaffolding through the owning
        ``create_vault_doc`` core.  Items apply sequentially and item
        failures do not abort the batch.  The affected feature indexes are
        regenerated as an automatic side effect.

        Args:
            ctx: The MCP request context.
            documents: The document specifications to scaffold.

        Returns:
            A batch result with a per-item outcome for every spec.
        """
        if not documents:
            raise ValueError("create requires at least one document spec")

        root_dir = _get_ctx().target_dir
        today = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d")

        await ctx.info(f"create: {len(documents)} document(s)")

        items: list[ItemResult] = []
        affected: set[str] = set()
        for idx, spec in enumerate(documents):
            item, feature = _create_one(root_dir, idx, spec, today)
            items.append(item)
            if feature is not None:
                affected.add(feature)

        if affected:
            _regenerate_indexes(root_dir, affected)

        await ctx.debug(f"create: {len(affected)} feature index(es) regenerated")
        return build_batch(items)

    @mcp.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    @_isolated_context
    async def edit(ctx: Context, operations: list[EditOperation]) -> BatchResult:
        """Apply one or more body-prose edits to vault documents.

        Each operation composes a full body (``set_body`` replaces it;
        ``append_section`` / ``replace_section`` address an existing section
        by exact heading text) and routes the write through the shared edit
        engine, which enforces the optional ``expected_blob_hash`` guard,
        runs pre-write conformance checks, and returns the post-write blob
        hash for chaining.  Frontmatter and filenames are never touched.

        Args:
            ctx: The MCP request context.
            operations: The body-prose operations to apply.

        Returns:
            A batch result with a per-item outcome for every operation.
        """
        if not operations:
            raise ValueError("edit requires at least one operation")

        root_dir = _get_ctx().target_dir
        await ctx.info(f"edit: {len(operations)} operation(s)")

        items = [_edit_one(root_dir, idx, op) for idx, op in enumerate(operations)]
        return build_batch(items)
