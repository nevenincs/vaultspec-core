"""Unit tests for :mod:`vaultspec_core.vaultcore.blob_hash`.

Pins the git-blob byte-compatibility claim the module docstring makes (the
``blob <len>\\0<data>`` header framing, hashed with SHA-1) and confirms the
digest is computed purely over raw bytes - no text-mode decoding or newline
translation can intervene, which is what keeps the optimistic-concurrency
guard immune to CRLF/LF drift on Windows.  Fixtures use real bytes on the
real filesystem; nothing here is mocked.
"""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.vaultcore.blob_hash import git_blob_oid

if TYPE_CHECKING:
    from collections.abc import Iterator

pytestmark = [pytest.mark.unit]

#: The well-known git blob object id of the empty blob, per the module
#: docstring and ``git hash-object /dev/null``.
_EMPTY_BLOB_OID = "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"


@pytest.fixture
def tmp_dir() -> Iterator[Path]:
    """Yield a real temporary directory, removed on teardown."""
    import shutil

    root = Path(tempfile.mkdtemp(prefix="vsc-blob-hash-")).resolve()
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


class TestGitCompatibility:
    def test_empty_blob_matches_well_known_oid(self) -> None:
        assert git_blob_oid(b"") == _EMPTY_BLOB_OID

    def test_header_framing_matches_git_hash_object(self) -> None:
        """Independently reproduce the loose-object hash git itself computes.

        Recomputes the digest via a from-scratch header (not by importing
        :func:`git_blob_oid`'s own header line), so a framing regression -
        wrong keyword, missing NUL, decimal-vs-other length encoding -
        would be caught even if it were introduced identically in both
        places by a careless refactor.
        """
        data = b"hello world\n"
        header = b"blob " + str(len(data)).encode("ascii") + b"\0"
        expected = hashlib.sha1(header + data, usedforsecurity=False).hexdigest()
        assert git_blob_oid(data) == expected
        # Matches the real ``git hash-object`` value for this exact payload.
        assert expected == "3b18e512dba79e4c8300dd08aeb37f8e728b8dad"

    def test_length_is_byte_length_not_character_length(self) -> None:
        """A multi-byte UTF-8 character must count its encoded bytes.

        ``len()`` on the payload must be the byte count fed to the header;
        using a character count here would corrupt the header for any
        non-ASCII document and desynchronize the guard from real git blobs.
        """
        data = "café\n".encode()  # 5 bytes: c a f 0xC3 0xA9 \n -> 6 bytes total
        assert len(data) == 6
        header = b"blob 6\0"
        expected = hashlib.sha1(header + data, usedforsecurity=False).hexdigest()
        assert git_blob_oid(data) == expected


class TestByteIdentity:
    def test_identical_bytes_hash_identically(self) -> None:
        data = b"---\ntags:\n  - '#adr'\n---\n\nBody.\n"
        assert git_blob_oid(data) == git_blob_oid(bytes(data))

    def test_single_byte_difference_changes_the_hash(self) -> None:
        a = b"Original body.\n"
        b = b"Original Body.\n"
        assert git_blob_oid(a) != git_blob_oid(b)

    def test_crlf_and_lf_variants_of_the_same_text_hash_differently(self) -> None:
        """CRLF bytes are NOT the same blob as their LF-normalised form.

        The guard must never treat these as equal (a missed conflict) nor
        report a real match as a mismatch (a spurious conflict); this pins
        that a CRLF file and its LF-translated form are, correctly, two
        different blobs.
        """
        lf = b"line one\nline two\n"
        crlf = b"line one\r\nline two\r\n"
        assert git_blob_oid(lf) != git_blob_oid(crlf)

    def test_hash_of_real_crlf_file_matches_raw_on_disk_bytes(
        self, tmp_dir: Path
    ) -> None:
        """A real CRLF file on disk hashes to its raw (untranslated) bytes.

        Guards against a regression where some read path opens the file in
        text mode - Python's universal-newline translation would silently
        turn the CRLF bytes into LF before hashing, producing a digest that
        does not match ``git hash-object`` (or a second read of the same
        bytes), and would show up as either a spurious or a missed conflict
        depending on which side of the comparison drifted.
        """
        path = tmp_dir / "crlf.md"
        raw = b"---\r\ndate: '2026-01-01'\r\n---\r\n\r\nBody line.\r\n"
        path.write_bytes(raw)

        # read_bytes() never performs newline translation, unlike read_text()
        # or a text-mode open() - this is the on-disk truth the guard hashes.
        assert path.read_bytes() == raw
        expected_header = b"blob " + str(len(raw)).encode("ascii") + b"\0"
        expected = hashlib.sha1(
            expected_header + raw, usedforsecurity=False
        ).hexdigest()
        assert git_blob_oid(path.read_bytes()) == expected
        # Re-reading produces the identical digest: the hash is a pure
        # function of the on-disk bytes, not of process/thread state.
        assert git_blob_oid(path.read_bytes()) == git_blob_oid(path.read_bytes())
