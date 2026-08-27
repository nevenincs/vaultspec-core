"""Strict reader for the release's aggregated ``SHA256SUMS``.

This module is the direct remedy for the defect that shipped
vaultspec-core-v0.1.60's Scoop manifest with empty hashes. Two things went
wrong there and both are refused here rather than tolerated:

1. The Windows build leg wrote its checksum sidecars with CRLF endings (a
   ``Path.write_text`` newline translation, fixed in
   ``dev.binaries.build_pyapp``), so the aggregate carried mixed endings and
   a whitespace-splitting lookup matched the asset name against
   ``"...msvc.exe\\r"``.
2. The lookup that missed returned an empty string, and the shell guard meant
   to catch that was inert, so the empty value was written to the manifest.

A missing or malformed entry is therefore an exception here, never a default.
The reader also rejects a carriage return outright instead of stripping it:
silently accepting the malformed input would let the build-side regression
reappear undetected, and the aggregate is also consumed by ``sha256sum -c``,
which this reader cannot repair on that tool's behalf.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

#: One ``sha256sum`` output line: digest, two spaces, filename.
_LINE = re.compile(r"^(?P<digest>[0-9a-f]{64})  (?P<name>\S.*)$")


class ChecksumError(ValueError):
    """The release's ``SHA256SUMS`` cannot be trusted to pin a manifest."""


def parse_checksums(text: str) -> dict[str, str]:
    """Return ``{asset name: digest}`` for one ``SHA256SUMS`` document.

    Raises :class:`ChecksumError` on a carriage return, a malformed line, or
    an asset listed twice with conflicting digests.
    """
    if "\r" in text:
        raise ChecksumError(
            "SHA256SUMS contains a carriage return: the build wrote mixed line "
            "endings, which breaks `sha256sum -c` and asset lookup by name",
        )
    digests: dict[str, str] = {}
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        match = _LINE.match(line)
        if match is None:
            raise ChecksumError(
                f"SHA256SUMS line {number} is not sha256sum format: {line!r}"
            )
        name = match["name"]
        digest = match["digest"]
        previous = digests.get(name)
        if previous is not None and previous != digest:
            raise ChecksumError(
                f"SHA256SUMS lists {name!r} twice with different digests"
            )
        digests[name] = digest
    if not digests:
        raise ChecksumError("SHA256SUMS is empty; the release attached no checksums")
    return digests


def read_checksums(path: Path) -> dict[str, str]:
    """Return ``{asset name: digest}`` for a ``SHA256SUMS`` file on disk."""
    # newline="" so the reader sees the file's real bytes; the default text
    # mode would translate CRLF to LF and hide the very defect being guarded.
    return parse_checksums(path.read_text(encoding="utf-8", newline=""))


def require(digests: dict[str, str], asset: str) -> str:
    """Return the digest for ``asset``, refusing to invent one when absent.

    The whole point of this function is that it has no fallback. An asset the
    release did not attach cannot be pinned, and a manifest that pins nothing
    is a broken install for whoever runs the package manager next.
    """
    digest = digests.get(asset)
    if digest is None:
        available = ", ".join(sorted(digests)) or "<none>"
        raise ChecksumError(
            f"release SHA256SUMS has no entry for {asset!r}; it lists: {available}",
        )
    return digest
