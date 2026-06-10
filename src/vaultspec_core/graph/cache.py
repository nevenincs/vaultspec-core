"""Fingerprint-keyed on-disk cache for the vault document graph.

Repeated one-shot reads (``vault graph``, ``vault link list``, MCP ``find``)
rebuild :class:`~vaultspec_core.graph.api.VaultGraph` from scratch: a full
``scan_vault`` walk, a full file read and parse of every document, full
link resolution, and the PageRank pass.  This module caches the *built*
canonical graph beside a fingerprint manifest so that an unchanged corpus
loads the serialised graph instead of re-parsing.

The cache is an optimisation and must be **sound**: a stale cache is never
trusted.  Soundness rests on three guards, in order of strength:

1. **File-set equality.**  The manifest fingerprints the complete set of
   scanned ``.md`` files.  A file added or removed since the cache was
   written changes the key set and invalidates the cache, even if no
   surviving file changed.
2. **Per-file size and mtime.**  Each file carries ``(st_size,
   st_mtime_ns)`` - the same primitive the repair pipeline uses in
   :mod:`vaultspec_core.vaultcore.repair`.  This is the cheap fast-path
   guard: almost every real edit changes the size or the modification time.
3. **Per-file content hash.**  Each file also carries a SHA-256 of its
   bytes.  ``st_mtime_ns`` resolution can theoretically miss a same-size
   edit applied within a single timestamp tick, so the content hash closes
   that window: validation requires the size, the mtime, *and* the hash to
   match.  The hash is read-once per file during fingerprinting, which is
   strictly cheaper than the parse-and-build the cache avoids, so it is
   always computed rather than gated behind a flag.

:func:`validate` returns ``True`` only when the current file set and every
per-file fingerprint match the manifest exactly.  Any divergence - a
changed, added, or removed file, an absent cache, or a corrupt/unreadable
cache file - is treated as a miss and forces a full rebuild.  The cache can
therefore be safely always-on: it can never serve data that does not match
the bytes currently on disk, and a corrupt cache degrades silently to a
rebuild rather than crashing or serving garbage.

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
from typing import TYPE_CHECKING, Any

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
#: misread.  Tied to the graph wire schema generation (``v2``).
CACHE_SCHEMA = "vaultspec.vault.graph.cache.v2"

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
    """

    schema: str
    manifest: dict[str, Fingerprint]
    graph: dict[str, Any]
    dangling_links: list[list[str]]


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


def fingerprint_vault(
    scanned_files: Iterable[Path],
    root_dir: Path,
) -> dict[str, Fingerprint]:
    """Compute the fingerprint manifest for the documents the graph consumes.

    Keyed on the exact file set passed in (the same iterable the graph
    build walks via ``scan_vault``) so the manifest cannot drift from the
    corpus the cached graph was built over.  Each file contributes its
    ``(st_size, st_mtime_ns, sha256_hex)`` fingerprint.  Files that cannot
    be stat-ed or read are skipped: a vanished file simply does not appear
    in the manifest, which is itself a file-set divergence that
    :func:`validate` detects on the next build.

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
            key = path.relative_to(root_dir).as_posix()
        except ValueError:
            key = path.as_posix()
        try:
            content_hash = _hash_file(path)
        except OSError:
            continue
        manifest[key] = (stat.st_size, stat.st_mtime_ns, content_hash)
    return manifest


def validate(
    manifest: dict[str, Fingerprint],
    current: dict[str, Fingerprint],
) -> bool:
    """Return ``True`` only when *current* matches the cached *manifest* exactly.

    The match is total: the two mappings must have the same set of keys
    (so an added or removed file invalidates) and identical fingerprint
    tuples for every key (so a changed size, mtime, or content hash
    invalidates).  Any divergence returns ``False``, forcing a full
    rebuild.  This is the single decision point behind "stale never
    trusted".

    Args:
        manifest: The fingerprint manifest stored in the cache.
        current: The freshly-computed fingerprint manifest for the vault
            as it exists on disk now.

    Returns:
        ``True`` when the manifests are equal, ``False`` otherwise.
    """
    if manifest.keys() != current.keys():
        return False
    return all(manifest[key] == current[key] for key in manifest)


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
    if data.get("schema") != CACHE_SCHEMA:
        logger.debug(
            "Graph cache schema mismatch at %s (%r != %r); ignoring",
            path,
            data.get("schema"),
            CACHE_SCHEMA,
        )
        return None

    raw_manifest = data.get("manifest")
    raw_graph = data.get("graph")
    raw_dangling = data.get("dangling_links")
    if not isinstance(raw_manifest, dict) or not isinstance(raw_graph, dict):
        return None
    if not isinstance(raw_dangling, list):
        return None

    manifest: dict[str, Fingerprint] = {}
    for key, value in raw_manifest.items():
        if (
            not isinstance(key, str)
            or not isinstance(value, list)
            or len(value) != 3
            or not isinstance(value[0], int)
            or not isinstance(value[1], int)
            or not isinstance(value[2], str)
        ):
            logger.debug("Graph cache manifest entry %r is malformed; ignoring", key)
            return None
        manifest[key] = (value[0], value[1], value[2])

    dangling: list[list[str]] = []
    for pair in raw_dangling:
        if (
            not isinstance(pair, list)
            or len(pair) != 2
            or not all(isinstance(item, str) for item in pair)
        ):
            return None
        dangling.append([pair[0], pair[1]])

    return GraphCachePayload(
        schema=CACHE_SCHEMA,
        manifest=manifest,
        graph=raw_graph,
        dangling_links=dangling,
    )


def save(
    path: Path,
    manifest: dict[str, Fingerprint],
    graph: dict[str, Any],
    dangling_links: list[tuple[str, str]],
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
    """
    from ..core.helpers import atomic_write

    payload = {
        "schema": CACHE_SCHEMA,
        "manifest": {key: list(value) for key, value in manifest.items()},
        "graph": graph,
        "dangling_links": [list(pair) for pair in dangling_links],
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(path, json.dumps(payload, default=str))
    except Exception as exc:
        logger.warning("Failed to persist graph cache at %s: %s", path, exc)
