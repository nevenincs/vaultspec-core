"""Unified query engine for .vault/ document operations.

Composes :mod:`.scanner` and :mod:`.parser` into a single query surface
used by CLI commands (``vaultspec-core vault stats``,
``vaultspec-core vault list``, ``vaultspec-core vault feature list``).
Exports :class:`VaultDocument`, :func:`list_documents`, :func:`get_stats`,
:func:`list_feature_details`, :func:`archive_feature`, and
:func:`rename_feature`.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..core.helpers import atomic_write
from .models import DocType, refresh_modified_stamp
from .parser import parse_frontmatter
from .rename_ops import rename_document_path, rewrite_incoming_refs
from .scanner import get_doc_type, scan_vault

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


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


def _scan_all(root_dir: Path) -> list[VaultDocument]:
    """Scan the vault and parse every document into a :class:`VaultDocument`.

    Used internally by :func:`list_documents`, :func:`get_stats`,
    :func:`list_feature_details`, and :mod:`vaultspec_core.vaultcore.checks.features`.

    Args:
        root_dir: Project root directory.

    Returns:
        List of :class:`VaultDocument` instances for all readable vault files.
    """
    docs = []
    for doc_path in scan_vault(root_dir):
        try:
            content = doc_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        meta, _ = parse_frontmatter(content)
        dt = get_doc_type(doc_path, root_dir)
        dt_str = dt.value if dt else "unknown"
        tags = meta.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]
        feature = _parse_feature_from_tags(tags, dt_str)
        # Fallback: if no feature from tags, check bare 'feature:' field
        if not feature and "feature" in meta:
            feature = str(meta["feature"]).lstrip("#").strip().lower() or None
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


def list_documents(
    root_dir: Path,
    *,
    doc_type: str | None = None,
    feature: str | None = None,
    date: str | None = None,
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

    Returns:
        Ordered list of :class:`VaultDocument` instances matching all
        supplied filters.
    """
    docs = _scan_all(root_dir)

    if doc_type == "orphaned":
        from ..graph import VaultGraph

        graph = VaultGraph(root_dir)
        orphan_names = set(graph.get_orphaned())
        docs = [d for d in docs if d.name in orphan_names]
    elif doc_type == "invalid":
        from ..graph import VaultGraph

        graph = VaultGraph(root_dir)
        dangling_sources = {src for src, _ in graph.get_dangling_links()}
        docs = [d for d in docs if d.name in dangling_sources]
    elif doc_type:
        docs = [d for d in docs if d.doc_type == doc_type]

    if feature:
        feature = feature.lstrip("#")
        docs = [d for d in docs if d.feature == feature]

    if date:
        docs = [d for d in docs if d.date == date]

    return docs


def get_stats(
    root_dir: Path,
    *,
    feature: str | None = None,
    doc_type: str | None = None,
    date: str | None = None,
) -> dict:
    """Compute vault statistics with optional filters.

    Args:
        root_dir: Project root directory.
        feature: Restrict counts to a single feature (without ``#``).
        doc_type: Restrict counts to a single document type.
        date: Restrict to documents matching this date (``YYYY-MM-DD``).

    Returns:
        Dict with keys: ``total_docs``, ``total_features``,
        ``counts_by_type`` (``dict[str, int]``), ``orphaned_count``,
        ``dangling_link_count``. Orphan and invalid counts are always
        computed against the full unfiltered vault via
        :class:`~vaultspec_core.graph.VaultGraph`.
    """
    docs = list_documents(root_dir, feature=feature, doc_type=doc_type, date=date)

    counts_by_type: dict[str, int] = {}
    features: set[str] = set()
    for d in docs:
        counts_by_type[d.doc_type] = counts_by_type.get(d.doc_type, 0) + 1
        if d.feature:
            features.add(d.feature)

    # Orphan/invalid counts from graph (unfiltered)
    from ..graph import VaultGraph

    try:
        graph = VaultGraph(root_dir)
        orphaned_count = len(graph.get_orphaned())
        dangling_link_count = len(graph.get_dangling_links())
    except (OSError, ValueError) as exc:
        logger.warning("Failed to build vault graph for stats: %s", exc)
        orphaned_count = 0
        dangling_link_count = 0

    return {
        "total_docs": len(docs),
        "total_features": len(features),
        "counts_by_type": counts_by_type,
        "orphaned_count": orphaned_count,
        "dangling_link_count": dangling_link_count,
    }


def list_feature_details(
    root_dir: Path,
    *,
    date: str | None = None,
    doc_type: str | None = None,
    orphaned_only: bool = False,
) -> list[dict]:
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
        List of dicts sorted by feature name, each with keys: ``name``,
        ``doc_count``, ``types`` (sorted list), ``earliest_date``,
        ``latest_activity``, ``has_plan``.
    """
    docs = _scan_all(root_dir)

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

    results = []
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


def archive_feature(root_dir: Path, feature: str, dry_run: bool = False) -> dict:
    """Move all documents for a feature into ``.vault/_archive/``.

    Preserves the per-type subdirectory structure under the archive folder.

    Args:
        root_dir: Project root directory.
        feature: Feature name to archive (leading ``#`` is stripped).
        dry_run: Preview planned changes.

    Returns:
        Dict with keys: ``archived_count`` (int), ``paths`` (list of
        strings -- new paths relative to ``root_dir``), ``cross_links`` (list),
        ``dry_run`` (bool).
    """
    import shutil

    from ..config import get_config
    from ..core.exceptions import VaultSpecError

    feature = feature.strip().lstrip("#").strip()
    if not feature:
        raise VaultSpecError(
            "A feature tag is required to archive. Refusing to run with an "
            "empty tag, which would match and archive every document.",
        )

    cfg = get_config()
    vault_dir = root_dir / cfg.docs_dir
    archive_dir = vault_dir / "_archive"

    docs = list_documents(root_dir, feature=feature)

    if not docs:
        raise VaultSpecError(f"Feature tag '{feature}' matches zero documents.")

    # Find cross-feature links
    cross_links = []
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

    archived: list[str] = []
    for doc in docs:
        # Preserve subdirectory (e.g., adr/, plan/)
        rel = doc.path.relative_to(vault_dir)
        dest = archive_dir / rel
        if not dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(doc.path), str(dest))
        archived.append(str(dest.relative_to(root_dir)))

    return {
        "archived_count": len(archived),
        "paths": archived,
        "cross_links": cross_links,
        "dry_run": dry_run,
    }


def unarchive_feature(root_dir: Path, feature: str, dry_run: bool = False) -> dict:
    """Move all documents for a feature from ``.vault/_archive/`` back to
    their original locations.

    Args:
        root_dir: Project root directory.
        feature: Feature name to unarchive (leading ``#`` is stripped).
        dry_run: Preview planned changes.

    Returns:
        Dict with keys: ``unarchived_count`` (int), ``paths`` (list of
        strings -- new paths relative to ``root_dir``), ``dry_run`` (bool).
    """
    import shutil

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
    vault_dir = root_dir / cfg.docs_dir
    archive_dir = vault_dir / "_archive"

    if not archive_dir.exists():
        raise VaultSpecError(
            f"Feature tag '{feature}' matches zero archived documents."
        )

    archived_docs = []
    for doc_path in archive_dir.rglob("*.md"):
        if ".obsidian" in doc_path.parts:
            continue
        try:
            content = doc_path.read_text(encoding="utf-8")
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

        feature_val = _parse_feature_from_tags(tags, dt_str)
        if not feature_val and "feature" in meta:
            feature_val = str(meta["feature"]).lstrip("#").strip().lower() or None

        if feature_val == feature.lower():
            archived_docs.append((doc_path, rel_path))

    if not archived_docs:
        raise VaultSpecError(
            f"Feature tag '{feature}' matches zero archived documents."
        )

    unarchived_paths: list[str] = []
    for doc_path, rel_path in archived_docs:
        dest = vault_dir / rel_path
        if not dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(doc_path), str(dest))
        unarchived_paths.append(str(dest.relative_to(root_dir)))

    if not dry_run:
        _cleanup_empty_dirs(archive_dir)

    return {
        "unarchived_count": len(unarchived_paths),
        "paths": unarchived_paths,
        "dry_run": dry_run,
    }


def _cleanup_empty_dirs(directory: Path) -> None:
    """Recursively delete empty subdirectories."""
    if not directory.exists() or not directory.is_dir():
        return
    for child in list(directory.iterdir()):
        if child.is_dir():
            _cleanup_empty_dirs(child)
    if directory.is_dir() and not list(directory.iterdir()):
        import contextlib

        with contextlib.suppress(OSError):
            directory.rmdir()


# ---------------------------------------------------------------------------
# Feature rename (``vaultspec-core vault feature rename``)
# ---------------------------------------------------------------------------
#
# ``rename_feature`` atomically renames a ``#feature`` across every binding
# surface: authored document filenames, the exec folder and exec record
# filenames, the ``#feature`` frontmatter tag, ``related:`` wiki-links, and
# the regenerated feature index.  Free-form body prose is never touched.
# The apply path records a reverse journal so that any mid-apply failure
# restores the vault byte-for-byte to its pre-rename state.

#: Kebab-case gate for a rename target, mirroring ``vault add`` time
#: (``vault_cmd.py``) and the schema feature-tag form (``models.py``).
_FEATURE_KEBAB_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_FEATURE_TAG_FORM_RE = re.compile(r"^#[a-z0-9-]+$")

#: A single block-sequence ``tags:`` entry, capturing the dash/indent
#: prefix, an optional surrounding quote, the ``#tag`` value, and any
#: trailing whitespace so the rewrite can preserve the original style.
_FEATURE_TAG_LINE_RE = re.compile(r"^(\s*-\s*)(['\"]?)(#[\w-]+)\2(\s*)$")

#: A ``related:`` block-sequence wiki-link entry, used by the read-only
#: dry-run predictor to estimate how many incoming links would be rewritten.
_RELATED_LINK_RE = re.compile(r'^\s*-\s*["\']?\[\[(.+?)\]\]["\']?.*$')


@dataclass
class _RenamePlan:
    """A fully-computed rename plan that mutates nothing on its own.

    Attributes:
        file_renames: ``(src, dst)`` pairs for every authored document and
            exec record whose filename carries the feature segment.
        exec_dir_renames: ``(old_folder, new_folder, plan_date)`` triples
            for every ``.vault/exec/{plan_date}-{feature}/`` folder.
        index_old_path: Path to the existing feature index, or ``None``.
        index_new_path: Path the regenerated index will occupy.
        stem_renames: ``(old_stem, new_stem)`` pairs fed to the
            ``related:`` wiki-link cascade.
        collisions: Per-file destination collisions that force a refusal.
    """

    file_renames: list[tuple[Path, Path]]
    exec_dir_renames: list[tuple[Path, Path, str]]
    index_old_path: Path | None
    index_new_path: Path
    stem_renames: list[tuple[str, str]]
    collisions: list[dict]


@dataclass
class _RenameJournal:
    """Reverse-journal capturing enough state to undo a partial apply.

    Attributes:
        file_renames: ``(src, dst)`` renames actually applied, in order.
        created_dirs: Directories created during apply (new exec folders,
            a freshly-created index directory).
        removed_dirs: Old exec folders removed once emptied during apply.
        created_files: Files created during apply (a brand-new index).
        snapshots: Original bytes of every file the apply may move or
            mutate, keyed by their pre-rename path.
    """

    file_renames: list[tuple[Path, Path]] = field(default_factory=list)
    created_dirs: list[Path] = field(default_factory=list)
    removed_dirs: list[Path] = field(default_factory=list)
    created_files: list[Path] = field(default_factory=list)
    snapshots: dict[Path, bytes] = field(default_factory=dict)


def _rel(path: Path, root_dir: Path) -> str:
    """Return *path* relative to *root_dir*, or its string form on failure."""
    try:
        return str(path.relative_to(root_dir))
    except ValueError:
        return str(path)


def _same_file(a: Path, b: Path) -> bool:
    """Return ``True`` when *a* and *b* identify the same on-disk file."""
    try:
        return a.samefile(b)
    except OSError:
        return False


# -- S05: validation helpers ------------------------------------------------


def _validate_feature_rename(
    root_dir: Path, old: str, new: str, *, force: bool
) -> tuple[str, str, list[VaultDocument]]:
    """Validate a feature rename request before any plan is computed.

    Enforces: non-empty source and target (after ``strip().lstrip('#')``);
    a target distinct from the source; a kebab-case, schema-valid target
    tag; a target that is not a reserved :class:`DocType` value; a source
    that matches at least one non-archived document; and - unless *force* -
    a target that currently owns zero documents.

    Args:
        root_dir: Project root directory.
        old: Raw source feature tag (leading ``#`` tolerated).
        new: Raw target feature tag (leading ``#`` tolerated).
        force: When ``True``, permit merging into an existing feature.

    Returns:
        ``(old_clean, new_clean, src_docs)`` - the normalised feature names
        and the source feature's documents.

    Raises:
        VaultSpecError: When any guard fails.
    """
    from ..core.exceptions import VaultSpecError

    old_clean = old.strip().lstrip("#").strip()
    new_clean = new.strip().lstrip("#").strip()

    if not old_clean:
        raise VaultSpecError(
            "A source feature tag is required to rename. Refusing to run with "
            "an empty tag, which would match every document."
        )
    if not new_clean:
        raise VaultSpecError(
            "A target feature tag is required to rename. Refusing to run with "
            "an empty target tag."
        )
    if old_clean == new_clean:
        raise VaultSpecError(
            f"Source and target feature are identical ('{old_clean}'); there "
            "is nothing to rename."
        )
    if not _FEATURE_KEBAB_RE.match(new_clean) or not _FEATURE_TAG_FORM_RE.match(
        f"#{new_clean}"
    ):
        raise VaultSpecError(
            f"Target feature '{new_clean}' is not a valid feature tag. It must "
            "be kebab-case matching ^[a-z0-9][a-z0-9-]*$ (e.g. 'editor-demo')."
        )
    reserved = {dt.value for dt in DocType}
    if new_clean in reserved:
        raise VaultSpecError(
            f"Target feature '{new_clean}' is a reserved document-type name "
            f"({', '.join(sorted(reserved))}). A feature tag with that name is "
            "invisible to the feature scanner; choose a different name."
        )

    src_docs = list_documents(root_dir, feature=old_clean)
    if not src_docs:
        raise VaultSpecError(f"Source feature '{old_clean}' matches zero documents.")

    if not force:
        dst_docs = list_documents(root_dir, feature=new_clean)
        if dst_docs:
            raise VaultSpecError(
                f"Target feature '{new_clean}' already has {len(dst_docs)} "
                "document(s). Re-run with --force to merge the source feature "
                "into it."
            )

    return old_clean, new_clean, src_docs


# -- S06: anchored, date-keyed feature-segment path transforms --------------


def _swap_authored_filename(name: str, old: str, new: str) -> str | None:
    """Swap only the feature segment of an authored-doc filename.

    Anchored on the ``YYYY-MM-DD`` date prefix and the ``-{old}-`` boundary,
    so a prefix collision (``old`` is a prefix of another feature) cannot
    over-match.  Any suffix after the feature segment - the type token and,
    for audits, an optional narrative topic infix - is preserved verbatim.

    Args:
        name: Bare filename (e.g. ``2026-06-26-old-adr.md`` or
            ``2026-06-26-old-perf-audit.md``).
        old: Current feature name (without ``#``).
        new: Replacement feature name (without ``#``).

    Returns:
        The rewritten filename, or ``None`` when *name* does not carry the
        ``{date}-{old}-`` feature segment.
    """
    pattern = rf"^(\d{{4}}-\d{{2}}-\d{{2}})-{re.escape(old)}(-.+\.md)$"
    m = re.match(pattern, name)
    if m is None:
        return None
    return f"{m.group(1)}-{new}{m.group(2)}"


def _match_exec_folder_date(folder_name: str, old: str) -> str | None:
    """Return the plan date of a ``{plan_date}-{old}`` exec folder, or ``None``."""
    m = re.match(rf"^(\d{{4}}-\d{{2}}-\d{{2}})-{re.escape(old)}$", folder_name)
    return m.group(1) if m else None


def _swap_exec_filename(name: str, plan_date: str, old: str, new: str) -> str | None:
    """Swap the feature segment of an exec record, preserving *plan_date*.

    The ``{plan_date}`` prefix is the parent plan's date - which may differ
    from the record's own ``date:`` frontmatter - and is held fixed; only
    the ``{old}`` token immediately after it is replaced.

    Args:
        name: Bare exec record filename
            (e.g. ``2026-06-26-old-P01-S01.md``).
        plan_date: The exec folder's date prefix.
        old: Current feature name (without ``#``).
        new: Replacement feature name (without ``#``).

    Returns:
        The rewritten filename, or ``None`` when *name* does not start with
        the ``{plan_date}-{old}-`` prefix.
    """
    prefix = f"{plan_date}-{old}-"
    if not name.startswith(prefix):
        return None
    return f"{plan_date}-{new}-{name[len(prefix) :]}"


# -- S07: feature tag-block rewriter ----------------------------------------


def _parse_inline_tags(after: str) -> list[str]:
    """Parse an inline (flow) ``tags:`` value into a list of tag strings.

    Args:
        after: The text following ``tags:`` on the key line, already
            stripped (e.g. ``"['#adr', '#old']"`` or ``"'#adr'"``).

    Returns:
        The tag strings in source order.

    Raises:
        VaultSpecError: When *after* is not a parseable YAML scalar or
            sequence of strings - raising here forces a refusal rather than
            writing corrupt YAML.
    """
    import yaml

    from ..core.exceptions import VaultSpecError

    try:
        parsed = yaml.safe_load(f"tags: {after}")
    except yaml.YAMLError as exc:
        raise VaultSpecError(
            f"Cannot parse inline tags value {after!r}: {exc}"
        ) from exc

    value = parsed.get("tags") if isinstance(parsed, dict) else None
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(t) for t in value]
    raise VaultSpecError(f"Inline tags value is not a sequence: {after!r}")


def _rewrite_feature_tag_block(content: str, old: str, new: str) -> tuple[str, bool]:
    """Rewrite the single ``#old`` feature tag to ``#new`` in ``tags:``.

    Operates strictly on the YAML ``tags:`` block inside the leading
    frontmatter fence; the directory tag, every other line, body prose, the
    CRLF/LF line-ending convention, and a leading UTF-8 BOM are preserved.
    A flow-style ``tags: ['#a', '#b']`` value is first normalised to block
    form (borrowing the approach in :mod:`.related_surgery`) so the rewrite
    is robust on imperfect inputs.

    Args:
        content: Full document text including frontmatter.
        old: Current feature name (without ``#``).
        new: Replacement feature name (without ``#``).

    Returns:
        ``(new_content, changed)`` where *changed* indicates whether the
        ``#old`` tag was present and rewritten.
    """
    old_tag = f"#{old}"
    new_tag = f"#{new}"

    bom = ""
    body = content
    if body.startswith("\ufeff"):
        bom = "\ufeff"
        body = body[1:]
    newline = "\r\n" if "\r\n" in body else "\n"
    had_trailing = body.endswith(("\r\n", "\n"))
    lines = body.splitlines()

    out: list[str] = []
    changed = False
    in_frontmatter = False
    fence = 0
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if stripped == "---":
            fence += 1
            out.append(line)
            i += 1
            if fence == 1:
                in_frontmatter = True
                continue
            # Closing fence reached: copy the remainder of the file verbatim.
            out.extend(lines[i:])
            break

        if not in_frontmatter:
            out.append(line)
            i += 1
            continue

        if stripped.startswith("tags:"):
            after = line.split("tags:", 1)[1].strip()
            indent = line[: len(line) - len(line.lstrip())]
            if after and after != "[]":
                # Inline / flow form: normalise to block form, swapping the
                # feature tag in the process.
                tag_list = _parse_inline_tags(after)
                new_list = [new_tag if t == old_tag else t for t in tag_list]
                if new_list != tag_list:
                    changed = True
                out.append(f"{indent}tags:")
                out.extend(f"{indent}  - '{t}'" for t in new_list)
                i += 1
                continue
            # Block form: walk the indented dash entries and rewrite the one
            # carrying the feature tag.
            out.append(line)
            i += 1
            while i < n:
                entry = lines[i]
                if entry.startswith((" ", "\t")) and entry.lstrip().startswith("-"):
                    m = _FEATURE_TAG_LINE_RE.match(entry)
                    if m is not None and m.group(3) == old_tag:
                        quote = m.group(2)
                        out.append(f"{m.group(1)}{quote}{new_tag}{quote}{m.group(4)}")
                        changed = True
                    else:
                        out.append(entry)
                    i += 1
                    continue
                break
            continue

        out.append(line)
        i += 1

    result = bom + newline.join(out)
    if had_trailing:
        result += newline
    return result, changed


# -- S08: plan computation + collision detection ----------------------------


def _compute_rename_plan(
    root_dir: Path, old: str, new: str, src_docs: list[VaultDocument]
) -> _RenamePlan:
    """Build the full rename plan without mutating anything on disk.

    Args:
        root_dir: Project root directory.
        old: Normalised source feature name.
        new: Normalised target feature name.
        src_docs: The source feature's documents (from
            :func:`list_documents`).

    Returns:
        A :class:`_RenamePlan` describing every file rename, exec-folder
        rename, the index plan, the wiki-link stem map, and any per-file
        destination collisions.

    Raises:
        VaultSpecError: When a document or exec folder does not match the
            expected feature-segment shape and so cannot be transformed.
    """
    from ..config import get_config
    from ..core.exceptions import VaultSpecError

    cfg = get_config()
    index_dir = root_dir / cfg.docs_dir / cfg.index_dir

    authored_renames: list[tuple[Path, Path]] = []
    exec_docs: list[VaultDocument] = []
    index_old_path: Path | None = None

    for doc in src_docs:
        if doc.doc_type == "index" or doc.name.endswith(".index"):
            index_old_path = doc.path
            continue
        if doc.doc_type == "exec":
            exec_docs.append(doc)
            continue
        new_name = _swap_authored_filename(doc.path.name, old, new)
        if new_name is None:
            raise VaultSpecError(
                f"Cannot derive a renamed filename for '{doc.path.name}': it "
                f"does not match the expected '{{date}}-{old}-<type>.md' shape."
            )
        authored_renames.append((doc.path, doc.path.with_name(new_name)))

    # Discover each distinct exec folder, then rename every record inside it.
    exec_folder_dates: dict[Path, str] = {}
    for doc in exec_docs:
        folder = doc.path.parent
        if folder in exec_folder_dates:
            continue
        plan_date = _match_exec_folder_date(folder.name, old)
        if plan_date is None:
            raise VaultSpecError(
                f"Exec folder '{folder.name}' does not match the expected "
                f"'{{date}}-{old}' shape; refusing to rename."
            )
        exec_folder_dates[folder] = plan_date

    exec_dir_renames: list[tuple[Path, Path, str]] = []
    exec_record_renames: list[tuple[Path, Path]] = []
    for folder, plan_date in exec_folder_dates.items():
        new_folder = folder.with_name(f"{plan_date}-{new}")
        exec_dir_renames.append((folder, new_folder, plan_date))
        for record in sorted(folder.glob("*.md")):
            if not record.is_file():
                continue
            new_name = _swap_exec_filename(record.name, plan_date, old, new)
            if new_name is None:
                raise VaultSpecError(
                    f"Cannot derive a renamed exec record filename for "
                    f"'{record.name}' in folder '{folder.name}'."
                )
            exec_record_renames.append((record, new_folder / new_name))

    file_renames = authored_renames + exec_record_renames

    # Collision detection: two sources mapping to one destination, or a file
    # already sitting at a destination (the merge hazard under --force).
    collisions: list[dict] = []
    seen_dest: dict[Path, Path] = {}
    for src, dst in file_renames:
        if dst in seen_dest:
            collisions.append(
                {
                    "destination": _rel(dst, root_dir),
                    "sources": [_rel(seen_dest[dst], root_dir), _rel(src, root_dir)],
                    "reason": "two source files map to the same destination",
                }
            )
        else:
            seen_dest[dst] = src
        if dst.is_file() and not _same_file(src, dst):
            collisions.append(
                {
                    "destination": _rel(dst, root_dir),
                    "sources": [_rel(src, root_dir)],
                    "reason": "a file already exists at the destination",
                }
            )

    index_new_path = index_dir / f"{new}.index.md"

    stem_renames: list[tuple[str, str]] = [
        (src.stem, dst.stem) for src, dst in file_renames
    ]
    if index_old_path is not None:
        stem_renames.append((f"{old}.index", f"{new}.index"))

    return _RenamePlan(
        file_renames=file_renames,
        exec_dir_renames=exec_dir_renames,
        index_old_path=index_old_path,
        index_new_path=index_new_path,
        stem_renames=stem_renames,
        collisions=collisions,
    )


def _analyze_cross_feature_links(
    root_dir: Path, docs: list[VaultDocument], feature: str
) -> list[dict]:
    """Find incoming wiki-links from other features (mirrors ``archive``).

    Unlike archive (which can only warn that these may dangle), a rename
    actually rewrites them; the analysis is reported for parity and so a
    caller can show what the cascade touched.

    Args:
        root_dir: Project root directory.
        docs: The feature's documents.
        feature: The feature name being renamed (without ``#``).

    Returns:
        A list of ``{source, target, source_path}`` dicts.
    """
    cross_links: list[dict] = []
    try:
        from ..graph import VaultGraph

        # ``use_cache=False`` so this read-only reporting pass never persists a
        # graph cache to disk - a dry-run must mutate nothing, and a real run
        # invalidates the cache from the CLI afterwards regardless.
        graph = VaultGraph(root_dir, use_cache=False)
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
    except Exception as exc:
        logger.warning("Could not analyze cross-feature links: %s", exc)
    return cross_links


def _predict_rewrites(
    root_dir: Path, plan: _RenamePlan, old: str, new: str
) -> tuple[int, int]:
    """Predict tag and incoming-link rewrite counts without mutating.

    Used only for the ``dry_run`` plan preview.  The tag count is exact (it
    runs the real rewriter in memory against each source file); the related
    count is an estimate of how many ``related:`` entries reference a renamed
    stem.

    Args:
        root_dir: Project root directory.
        plan: The computed rename plan.
        old: Normalised source feature name.
        new: Normalised target feature name.

    Returns:
        ``(predicted_tag_rewrites, predicted_related_rewrites)``.
    """
    from ..config import get_config

    tag_rewrites = 0
    for src, _dst in plan.file_renames:
        try:
            text = src.read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        _new_text, changed = _rewrite_feature_tag_block(text, old, new)
        if changed:
            tag_rewrites += 1

    old_stems = {o.lower() for o, n in plan.stem_renames if o != n}
    related_rewrites = 0
    if old_stems:
        docs_dir = root_dir / get_config().docs_dir
        if docs_dir.is_dir():
            for md in docs_dir.rglob("*.md"):
                rel_parts = md.relative_to(docs_dir).parts
                if any(p == "_archive" or p.startswith(".") for p in rel_parts):
                    continue
                if not md.is_file():
                    continue
                related_rewrites += _count_related_refs(md, old_stems)

    return tag_rewrites, related_rewrites


def _count_related_refs(md_path: Path, old_stems_lower: set[str]) -> int:
    """Count ``related:`` wiki-link entries whose stem is in *old_stems_lower*."""
    try:
        text = md_path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return 0

    count = 0
    in_frontmatter = False
    in_related = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "---":
            if not in_frontmatter:
                in_frontmatter = True
                continue
            break
        if not in_frontmatter:
            continue
        if stripped.startswith("related:"):
            in_related = True
            continue
        if in_related and line and not line.startswith((" ", "\t", "-")):
            in_related = False
        if not in_related:
            continue
        m = _RELATED_LINK_RE.match(line)
        if m is None:
            continue
        target = m.group(1)
        for cut in ("#", "|"):
            idx = target.find(cut)
            if idx >= 0:
                target = target[:idx]
        if target.strip().lower() in old_stems_lower:
            count += 1
    return count


# -- S09: reverse-journal apply with rollback -------------------------------


def _snapshot_docs(root_dir: Path, journal: _RenameJournal) -> None:
    """Snapshot the original bytes of every non-archive ``*.md`` under docs.

    This is the simplest correct basis for rollback: any file the apply may
    move (renamed docs) or rewrite (the renamed docs' tag blocks, the
    vault-wide ``related:`` cascade, the modified-stamp refresh, the deleted
    old index) is captured by its pre-rename path so the reverse walk can
    restore it byte-for-byte.

    Args:
        root_dir: Project root directory.
        journal: The journal to populate.
    """
    from ..config import get_config

    docs_dir = root_dir / get_config().docs_dir
    if not docs_dir.is_dir():
        return
    for md in docs_dir.rglob("*.md"):
        try:
            rel_parts = md.relative_to(docs_dir).parts
        except ValueError:
            continue
        if any(p == "_archive" or p.startswith(".") for p in rel_parts):
            continue
        if not md.is_file():
            continue
        try:
            journal.snapshots[md] = md.read_bytes()
        except OSError as exc:
            logger.warning("Could not snapshot %s for rollback: %s", md, exc)


def _regenerate_feature_index(
    root_dir: Path, new: str, journal: _RenameJournal, index_dir_existed: bool
) -> Path:
    """Regenerate the feature index for *new* from a freshly-built graph.

    A non-cached :class:`~vaultspec_core.graph.VaultGraph` is built so the
    just-renamed (and now ``#new``-tagged) documents are observed.

    Args:
        root_dir: Project root directory.
        new: Normalised target feature name.
        journal: Journal to record a created index file / directory into.
        index_dir_existed: Whether the index directory existed before apply.

    Returns:
        Path to the regenerated index file.
    """
    from ..config import get_config
    from ..graph import VaultGraph
    from .index import generate_feature_index

    cfg = get_config()
    index_path = root_dir / cfg.docs_dir / cfg.index_dir / f"{new}.index.md"
    existed = index_path.exists()

    graph = VaultGraph(root_dir, use_cache=False)
    nodes = graph.get_feature_nodes(new)
    path = generate_feature_index(root_dir, new, nodes=nodes)
    if not index_dir_existed and path.parent.is_dir():
        journal.created_dirs.append(path.parent)
    if not existed:
        journal.created_files.append(path)
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


def _rollback_rename(journal: _RenameJournal) -> None:
    """Walk *journal* in reverse to restore the pre-rename vault state.

    The order is deliberate: delete created files first, recreate removed
    exec folders so renamed records have a home to return to, reverse the
    file renames (LIFO), drop any directories created during apply, and
    finally restore every snapshot's original bytes (which also recreates
    the deleted old index).

    Args:
        journal: The populated reverse journal.
    """
    import contextlib
    import shutil

    for path in journal.created_files:
        with contextlib.suppress(OSError):
            if path.is_file():
                path.unlink()

    for directory in journal.removed_dirs:
        with contextlib.suppress(OSError):
            directory.mkdir(parents=True, exist_ok=True)

    for src, dst in reversed(journal.file_renames):
        if not dst.exists():
            continue
        if rename_document_path(dst, src):
            continue
        with contextlib.suppress(OSError):
            shutil.move(str(dst), str(src))

    for directory in reversed(journal.created_dirs):
        with contextlib.suppress(OSError):
            if directory.is_dir() and not any(directory.iterdir()):
                directory.rmdir()

    for path, original in journal.snapshots.items():
        try:
            if not path.exists() or path.read_bytes() != original:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(original)
        except OSError as exc:
            logger.warning("Rollback could not restore %s: %s", path, exc)


def _apply_rename_plan(root_dir: Path, plan: _RenamePlan, old: str, new: str) -> dict:
    """Apply *plan* under a reverse journal, rolling back on any failure.

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

    journal = _RenameJournal()
    _snapshot_docs(root_dir, journal)

    cfg = get_config()
    index_dir = root_dir / cfg.docs_dir / cfg.index_dir
    index_dir_existed = index_dir.exists()

    try:
        # (1) Ensure destination exec folders exist before any record moves.
        for _old_folder, new_folder, _date in plan.exec_dir_renames:
            if not new_folder.exists():
                new_folder.mkdir(parents=True, exist_ok=True)
                journal.created_dirs.append(new_folder)

        # (2) Rename every authored doc and exec record.
        for src, dst in plan.file_renames:
            if not rename_document_path(src, dst):
                raise VaultSpecError(
                    f"Filesystem rename failed: {_rel(src, root_dir)} -> "
                    f"{_rel(dst, root_dir)} (destination may already exist)."
                )
            journal.file_renames.append((src, dst))

        # (3) Remove now-empty old exec folders.
        for old_folder, _new_folder, _date in plan.exec_dir_renames:
            if old_folder.is_dir() and not any(old_folder.iterdir()):
                old_folder.rmdir()
                journal.removed_dirs.append(old_folder)

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

        # (6) Cascade ``related:`` wiki-link rewrites across the vault, skipping
        #     ``_archive`` so a rename never mutates archived documents - they
        #     are out of scope per the ADR and are not snapshotted for rollback.
        cascade = CheckResult(check_name="feature-rename")
        rewrite_incoming_refs(
            root_dir, plan.stem_renames, cascade, exclude_dirs=frozenset({"_archive"})
        )
        related_rewrites = cascade.fixed_count
        cascade_paths: set[Path] = set()
        for diag in cascade.diagnostics:
            if diag.path is None:
                continue
            abs_path = diag.path if diag.path.is_absolute() else root_dir / diag.path
            cascade_paths.add(abs_path)

        # (7) Regenerate the index for the new feature from a fresh graph.
        new_index_path = _regenerate_feature_index(
            root_dir, new, journal, index_dir_existed
        )

        # (8) Refresh the modified stamp on every renamed or relinked doc.
        _refresh_rename_stamps(plan.file_renames, cascade_paths)

        return {
            "tag_rewrites": tag_rewrites,
            "related_rewrites": related_rewrites,
            "new_index_path": new_index_path,
        }
    except Exception as exc:
        _rollback_rename(journal)
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
) -> dict:
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
        A dict with at least: ``old``, ``new``, ``renamed_count``, ``paths``
        (``[{old, new}]`` rel-paths), ``exec_folders`` (``[{old, new}]``),
        ``tag_rewrites``, ``related_rewrites``, ``link_renames``
        (``[{old, new}]`` stems), ``index`` (``{old, new}``),
        ``cross_links``, ``collisions``, ``dry_run``, and a canonical
        ``status`` (``"unchanged"`` for a dry-run preview, ``"updated"``
        once applied).

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

    paths = [
        {"old": _rel(src, root_dir), "new": _rel(dst, root_dir)}
        for src, dst in plan.file_renames
    ]
    exec_folders = [
        {"old": _rel(old_folder, root_dir), "new": _rel(new_folder, root_dir)}
        for old_folder, new_folder, _date in plan.exec_dir_renames
    ]
    link_renames = [{"old": o, "new": n} for o, n in plan.stem_renames]
    index_info: dict = {
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
