"""Git blob object-id computation, byte-compatible with ``git hash-object``.

A vault document's identity on the wire is the git SHA-1 *blob* object id
of its raw bytes - the same value ``git hash-object`` prints and the same
value the dashboard engine derives over a file's bytes for optimistic
concurrency.  The hash is computed purely with :mod:`hashlib`; no ``git``
subprocess is spawned, so the helper works in an unindexed worktree and
on hosts without a git binary.

The git blob object is the bytes ``b"blob <len>\\0<data>"`` hashed with
SHA-1, where ``<len>`` is the decimal byte length of the payload.  This is
git's loose-object header convention; the empty blob therefore hashes to
the well-known ``e69de29bb2d1d6434b8b29ae775ad8c2e48c5391``.
"""

from __future__ import annotations

import hashlib

__all__ = ["git_blob_oid"]


def git_blob_oid(data: bytes) -> str:
    """Return the git SHA-1 blob object id of *data*.

    Byte-for-byte equivalent to ``git hash-object`` (and to the dashboard
    engine's gix blob OID) over the same payload.

    Args:
        data: The raw file bytes to hash.  Callers that hold document text
            must encode it (UTF-8) before calling so the hash matches the
            on-disk bytes.

    Returns:
        The 40-character lowercase hexadecimal SHA-1 blob object id.
    """
    header = b"blob " + str(len(data)).encode("ascii") + b"\0"
    return hashlib.sha1(header + data, usedforsecurity=False).hexdigest()
