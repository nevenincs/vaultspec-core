"""Fingerprint-keyed on-disk cache for the vault document graph.

Repeated one-shot reads (``vault graph``, ``vault link list``, MCP ``find``)
rebuild :class:`~vaultspec_core.graph.api.VaultGraph` from scratch: a full
``scan_vault`` walk, a full file read and parse of every document, full
link resolution, and the PageRank pass.  This module caches the *built*
canonical graph beside a fingerprint manifest so that an unchanged corpus
loads the serialised graph instead of re-parsing.

The cache is an optimisation and must stay **sound** without its own
validation costing more than the rebuild it avoids.  Soundness rests on
three guards, applied per git's racily-clean rule:

1. **File-set equality.**  The manifest fingerprints the complete set of
   scanned ``.md`` files.  A file added or removed since the cache was
   written changes the key set and invalidates the cache, even if no
   surviving file changed.
2. **Per-file size and mtime.**  Each file carries ``(st_size,
   st_mtime_ns)`` - the same primitive the repair pipeline uses in
   :mod:`vaultspec_core.vaultcore.repair`.  A size or mtime divergence is
   always a miss, and a match is *trusted* for any file whose mtime is
   strictly older than the cache file's own mtime: such a file cannot have
   been edited after the manifest recorded it without moving its mtime.
3. **Per-file content hash, racily-clean files only.**  A file whose mtime
   is not older than the cache write ("racy": edited within the same
   timestamp tick the cache was written in, or under clock skew) cannot be
   proven clean by stat alone, so exactly those files are re-hashed against
   the manifest's stored SHA-256.  On nanosecond-resolution filesystems
   (NTFS, ext4) the racy set is empty or near-empty; on coarse-resolution
   filesystems it grows to cover the wider tick.  Passing ``deep=True``
   hashes every file regardless - the explicit deep-verification path for
   doctor-class diagnostics.

:func:`validate` returns ``True`` only when the current file set matches
the manifest and every per-file guard passes.  Any divergence - a changed,
added, or removed file, an absent cache, or a corrupt/unreadable cache
file - is treated as a miss and forces a full rebuild.  The accepted
residual risk is a same-size edit that lands in the same mtime tick as a
*document* write recorded in the manifest while the cache file itself
carries a newer tick and the edit bypasses the mutating CLI verbs (which
drop the cache file); that window is bounded by one filesystem timestamp
tick and closable on demand with ``deep=True``.

The serialised graph store is JSON (networkx node-link format) rather than
pickle.  JSON is inspectable, diff-friendly, version-safe across Python
releases, and refuses to execute arbitrary code on load; the canonical
graph carries only JSON-friendly scalar attributes already (see
:meth:`~vaultspec_core.graph.api.DocNode.to_nx_attrs`), so JSON loses
nothing the graph needs to round-trip.

Exports:
    :data:`CACHE_SCHEMA`: Version string stamped into every cache file.
    :class:`GraphCachePayload`: The parsed contents of a cache file.
    :func:`fingerprint_vault`: Compute the manifest for the current vault.
    :func:`validate`: Decide whether a manifest still matches disk.
    :func:`load`: Read and parse a cache file, or ``None`` on any failure.
    :func:`save`: Atomically write a cache file.
    :func:`cache_path`: Resolve the cache file location for a vault root.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

logger = logging.getLogger(__name__)

__all__ = [
    "CACHE_SCHEMA",
    "GraphCachePayload",
    "cache_path",
    "fingerprint_vault",
    "load",
    "save",
    "validate",
]

#: Schema string stamped into every cache file.  Bump when the on-disk
#: payload shape changes so an older cache is treated as a miss rather than
#: misread.  Tied to the graph wire schema generation (``v3``).
CACHE_SCHEMA = "vaultspec.vault.graph.cache.v4"

#: Manifest value type: ``(st_size, st_mtime_ns, sha256_hex)`` per file.
Fingerprint = tuple[int, int, str]


@dataclass(frozen=True)
class GraphCachePayload:
    """Parsed contents of a graph cache file.

    Attributes:
        schema: The :data:`CACHE_SCHEMA` string the file was written with.
        manifest: Mapping of each scanned file's vault-relative POSIX path
            to its :data:`Fingerprint`.
        graph: The networkx node-link ``dict`` of the cached canonical
            graph, exactly as produced by
            :func:`networkx.readwrite.json_graph.node_link_data` with
            ``edges="edges"``.
        dangling_links: The ``(source, target)`` dangling-link pairs
            recorded during the cached build, as two-element lists.
        encoding_issues: The read and decode failures the cached build's
            ingress read observed, as ``(path, kind, detail, start)`` rows.
            Persisted because a document that fails to decode never enters
            the serialised graph, so a cache hit would otherwise restore a
            corpus that silently claims every file read cleanly.
    """

    schema: str
    manifest: dict[str, Fingerprint]
    graph: dict[str, Any]
    dangling_links: list[list[str]]
    encoding_issues: list[tuple[str, str, str, int | None]]


def cache_path(root_dir: Path) -> Path:
    """Return the cache file path for a vault *root_dir*.

    The cache lives under ``<docs_dir>/data/.graph-cache/graph.json``.  The
    ``data`` subdirectory is an auxiliary (non-document) vault directory and
    is excluded from the document scan, so the cache file is never itself
    treated as a vault document or fingerprinted.

    Args:
        root_dir: Project root that contains the docs directory.

    Returns:
        Absolute path to the JSON cache file (which may not yet exist).
    """
    from ..config import get_config

    docs_dir = root_dir / get_config().docs_dir
    return docs_dir / "data" / ".graph-cache" / "graph.json"


def _hash_file(path: Path) -> str:
    """Return the hex SHA-256 of *path*'s bytes.

    Args:
        path: File to hash.

    Returns:
        Lowercase hex digest string.

    Raises:
        OSError: When the file cannot be read.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_key(path: Path, root_dir: Path) -> str:
    """Return the stable vault-relative POSIX manifest key for *path*."""
    try:
        return path.relative_to(root_dir).as_posix()
    except ValueError:
        return path.as_posix()


def fingerprint_vault(
    scanned_files: Iterable[Path],
    root_dir: Path,
) -> dict[str, Fingerprint]:
    """Compute the fingerprint manifest for the documents the graph consumes.

    Called on the *save* path only, after a rebuild: the warm-read path
    validates against the stored manifest with :func:`validate` and never
    recomputes full hashes.  Keyed on the exact file set passed in (the
    same iterable the graph build walks via ``scan_vault``) so the manifest
    cannot drift from the corpus the cached graph was built over.  Each
    file contributes its ``(st_size, st_mtime_ns, sha256_hex)``
    fingerprint.  Files that cannot be stat-ed or read are skipped: a
    vanished file simply does not appear in the manifest, which is itself a
    file-set divergence that :func:`validate` detects on the next build.

    Args:
        scanned_files: The document paths the graph build observed (e.g.
            the output of ``scan_vault``).
        root_dir: Project root, used to derive stable vault-relative keys.

    Returns:
        Mapping of vault-relative POSIX path to :data:`Fingerprint`.
    """
    manifest: dict[str, Fingerprint] = {}
    for path in scanned_files:
        try:
            stat = path.stat()
        except OSError:
            continue
        try:
            content_hash = _hash_file(path)
        except OSError:
            continue
        manifest[_manifest_key(path, root_dir)] = (
            stat.st_size,
            stat.st_mtime_ns,
            content_hash,
        )
    return manifest


def validate(
    manifest: dict[str, Fingerprint],
    scanned_files: Iterable[Path],
    root_dir: Path,
    *,
    cache_mtime_ns: int | None,
    deep: bool = False,
) -> bool:
    """Return ``True`` only when the corpus on disk still matches *manifest*.

    Applies the racily-clean rule (see the module docstring): the file set
    must be identical, every file's ``(st_size, st_mtime_ns)`` must match
    the manifest, and files whose mtime is not older than *cache_mtime_ns*
    (the cache file's own mtime) are additionally content-hashed against
    the manifest because stat alone cannot prove them clean.  Any
    divergence returns ``False``, forcing a full rebuild.

    Args:
        manifest: The fingerprint manifest stored in the cache.
        scanned_files: The document paths of the vault as it exists on
            disk now (e.g. the output of ``scan_vault``).
        root_dir: Project root, used to derive stable vault-relative keys.
        cache_mtime_ns: The cache file's ``st_mtime_ns``, the racily-clean
            reference point.  ``None`` (unknown) treats every file as racy,
            degrading to full hash validation - sound, never unsound.
        deep: When ``True``, content-hash every file regardless of mtime -
            the explicit deep-verification path.

    Returns:
        ``True`` when every guard passes for every file, ``False``
        otherwise.
    """
    seen: set[str] = set()
    for path in scanned_files:
        try:
            stat = path.stat()
        except OSError:
            # A vanished file is absent from the seen set; the final
            # file-set equality check reports the divergence.
            continue
        key = _manifest_key(path, root_dir)
        seen.add(key)
        entry = manifest.get(key)
        if entry is None:
            return False
        size, mtime_ns, content_hash = entry
        if stat.st_size != size or stat.st_mtime_ns != mtime_ns:
            return False
        racy = cache_mtime_ns is None or stat.st_mtime_ns >= cache_mtime_ns
        if deep or racy:
            try:
                if _hash_file(path) != content_hash:
                    return False
            except OSError:
                return False
    return seen == manifest.keys()


def _is_fingerprint_row(value: object) -> bool:
    """Return ``True`` when *value* is a serialised :data:`Fingerprint`.

    A manifest value round-trips through JSON as the three-element list
    ``[st_size, st_mtime_ns, sha256_hex]``.  The shape check precedes the
    per-element checks so element access is only reached once *value* is
    known to be a list of exactly three items.

    Args:
        value: A decoded JSON value from a cache file's manifest.

    Returns:
        ``True`` when the row can be read back as a fingerprint.
    """
    if not isinstance(value, list):
        return False
    items = cast("list[Any]", value)
    if len(items) != 3:
        return False
    size, mtime_ns, content_hash = items
    return (
        isinstance(size, int)
        and isinstance(mtime_ns, int)
        and isinstance(content_hash, str)
    )


def _is_encoding_issue_row(row: object) -> bool:
    """Return ``True`` when *row* is a serialised encoding-issue tuple.

    An encoding issue round-trips through JSON as the four-element list
    ``[path, kind, detail, start]``, where ``start`` is the optional byte
    offset of the failure and so may be ``null``.  As above, the shape
    check precedes the per-element checks.

    Args:
        row: A decoded JSON value from a cache file's issue list.

    Returns:
        ``True`` when the row can be read back as an encoding issue.
    """
    if not isinstance(row, list):
        return False
    items = cast("list[Any]", row)
    if len(items) != 4:
        return False
    doc_path, kind, detail, start = items
    return (
        isinstance(doc_path, str)
        and isinstance(kind, str)
        and isinstance(detail, str)
        and (start is None or isinstance(start, int))
    )


def _read_cache_json(path: Path) -> dict[str, Any] | None:
    """Read *path* and return its parsed JSON payload if the schema matches.

    Args:
        path: Path to the JSON cache file.

    Returns:
        The parsed top-level JSON object when the file is readable, valid
        JSON, and stamped with :data:`CACHE_SCHEMA`; ``None`` otherwise.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        logger.debug("Graph cache at %s is not valid JSON; ignoring", path)
        return None
    if not isinstance(data, dict):
        return None
    payload = cast("dict[str, Any]", data)
    if payload.get("schema") != CACHE_SCHEMA:
        logger.debug(
            "Graph cache schema mismatch at %s (%r != %r); ignoring",
            path,
            payload.get("schema"),
            CACHE_SCHEMA,
        )
        return None
    return payload


def _extract_cache_sections(
    data: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], list[Any], list[Any]] | None:
    """Pull and type-check the four top-level cache sections from *data*.

    Args:
        data: The parsed top-level JSON object from a cache file.

    Returns:
        The ``(manifest, graph, dangling_links, encoding_issues)`` raw
        values when all four are present with the expected container
        type; ``None`` when any section is missing or malformed.
    """
    raw_manifest = data.get("manifest")
    raw_graph = data.get("graph")
    raw_dangling = data.get("dangling_links")
    raw_encoding = data.get("encoding_issues")
    if not isinstance(raw_manifest, dict) or not isinstance(raw_graph, dict):
        return None
    if not isinstance(raw_dangling, list) or not isinstance(raw_encoding, list):
        return None
    manifest = cast("dict[str, Any]", raw_manifest)
    graph = cast("dict[str, Any]", raw_graph)
    dangling = cast("list[Any]", raw_dangling)
    encoding = cast("list[Any]", raw_encoding)
    return manifest, graph, dangling, encoding


def _parse_manifest(raw_manifest: dict[str, Any]) -> dict[str, Fingerprint] | None:
    """Validate and convert a cache file's raw manifest mapping.

    Args:
        raw_manifest: The decoded JSON ``manifest`` mapping.

    Returns:
        The mapping keyed by vault-relative path to :data:`Fingerprint`, or
        ``None`` when any entry is malformed.
    """
    manifest: dict[str, Fingerprint] = {}
    for key, value in raw_manifest.items():
        if not _is_fingerprint_row(value):
            logger.debug("Graph cache manifest entry %r is malformed; ignoring", key)
            return None
        manifest[key] = (value[0], value[1], value[2])
    return manifest


def _parse_dangling(raw_dangling: list[Any]) -> list[list[str]] | None:
    """Validate and convert a cache file's raw dangling-link list.

    Args:
        raw_dangling: The decoded JSON ``dangling_links`` list.

    Returns:
        The ``[source, target]`` pairs, or ``None`` when any row is
        malformed.
    """
    dangling: list[list[str]] = []
    for pair in raw_dangling:
        if not isinstance(pair, list):
            return None
        pair_items = cast("list[Any]", pair)
        if len(pair_items) != 2:
            return None
        first, second = pair_items
        if not isinstance(first, str) or not isinstance(second, str):
            return None
        dangling.append([first, second])
    return dangling


def _parse_encoding_issues(
    raw_encoding: list[Any],
) -> list[tuple[str, str, str, int | None]] | None:
    """Validate and convert a cache file's raw encoding-issues list.

    Args:
        raw_encoding: The decoded JSON ``encoding_issues`` list.

    Returns:
        The ``(path, kind, detail, start)`` rows, or ``None`` when any row
        is malformed.
    """
    encoding: list[tuple[str, str, str, int | None]] = []
    for row in raw_encoding:
        if not _is_encoding_issue_row(row):
            logger.debug(
                "Graph cache encoding-issue row %r is malformed; ignoring", row
            )
            return None
        encoding.append((row[0], row[1], row[2], row[3]))
    return encoding


def load(path: Path) -> GraphCachePayload | None:
    """Read and parse a cache file, returning ``None`` on any failure.

    A missing file, unreadable bytes, malformed JSON, a schema mismatch,
    or a structurally invalid payload all resolve to ``None`` so the
    caller falls back to a full rebuild.  The cache never raises into the
    build path: an unreadable cache is a miss, not an error.

    Args:
        path: Path to the JSON cache file.

    Returns:
        A :class:`GraphCachePayload` on success, or ``None`` when the file
        is absent, corrupt, or written with a different schema.
    """
    data = _read_cache_json(path)
    if data is None:
        return None
    sections = _extract_cache_sections(data)
    if sections is None:
        return None
    raw_manifest, raw_graph, raw_dangling, raw_encoding = sections

    manifest = _parse_manifest(raw_manifest)
    if manifest is None:
        return None
    dangling = _parse_dangling(raw_dangling)
    if dangling is None:
        return None
    encoding = _parse_encoding_issues(raw_encoding)
    if encoding is None:
        return None

    return GraphCachePayload(
        schema=CACHE_SCHEMA,
        manifest=manifest,
        graph=raw_graph,
        dangling_links=dangling,
        encoding_issues=encoding,
    )


def save(
    path: Path,
    manifest: dict[str, Fingerprint],
    graph: dict[str, Any],
    dangling_links: list[tuple[str, str]],
    encoding_issues: list[tuple[str, str, str, int | None]] | None = None,
) -> None:
    """Atomically write a cache file for a freshly-built graph.

    Creates the parent directory if needed and writes via the shared
    atomic temp-file-and-rename helper so a concurrent reader never
    observes a half-written cache.  Write failures are logged and
    swallowed: failing to persist the cache must never break the graph
    build that produced it.

    Args:
        path: Destination cache file path.
        manifest: The fingerprint manifest for the built corpus.
        graph: The networkx node-link ``dict`` of the canonical graph.
        dangling_links: The ``(source, target)`` dangling pairs recorded
            during the build.
        encoding_issues: The ``(path, kind, detail, start)`` read and decode
            failures the build's ingress read observed. A file that fails to
            decode never becomes a usable node, so without this the cache
            would restore a corpus that appears to have read cleanly.
    """
    from ..core.helpers import atomic_write

    payload = {
        "schema": CACHE_SCHEMA,
        "manifest": {key: list(value) for key, value in manifest.items()},
        "graph": graph,
        "dangling_links": [list(pair) for pair in dangling_links],
        "encoding_issues": [list(row) for row in (encoding_issues or [])],
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(path, json.dumps(payload, default=str))
    except Exception as exc:
        logger.warning("Failed to persist graph cache at %s: %s", path, exc)
