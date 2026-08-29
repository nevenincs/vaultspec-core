"""Guards for the strict ``SHA256SUMS`` reader.

Every case here is a way the release's checksum aggregate can be wrong. The
reader's contract is that none of them produce a usable value: a channel
manifest pinned from a bad aggregate is a broken install the maintainer never
sees and the user always does.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from dev.packaging.checksums import (
    ChecksumError,
    parse_checksums,
    read_checksums,
    require,
)

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.unit

DIGEST_A = "7452312e47a9eb7a7674174d359b78dd9689b60b1c6c955ac39387a71c42a365"
DIGEST_B = "a3794b80af72b16e030825590c6664113c20e7e10e4ae18d983636916e9f1f2a"


def test_parses_a_well_formed_aggregate() -> None:
    """The two-space sha256sum format maps asset names to digests."""
    text = (
        f"{DIGEST_A}  core-x86_64-unknown-linux-gnu\n"
        f"{DIGEST_B}  mcp-x86_64-unknown-linux-gnu\n"
    )

    assert parse_checksums(text) == {
        "core-x86_64-unknown-linux-gnu": DIGEST_A,
        "mcp-x86_64-unknown-linux-gnu": DIGEST_B,
    }


def test_rejects_a_carriage_return_rather_than_stripping_it() -> None:
    """The exact defect that emptied vaultspec-core-v0.1.60's Scoop hashes.

    Stripping would paper over a build-side regression that also breaks
    ``sha256sum -c`` for the affected rows, which this reader cannot fix on
    that tool's behalf. So it refuses.
    """
    text = f"{DIGEST_A}  core-x86_64-pc-windows-msvc.exe\r\n"

    with pytest.raises(ChecksumError, match="carriage return"):
        parse_checksums(text)


@pytest.mark.parametrize(
    "line",
    [
        "not-a-digest  core-x86_64-unknown-linux-gnu",
        f"{DIGEST_A} core-x86_64-unknown-linux-gnu",
        f"{DIGEST_A}  ",
        f"{DIGEST_A[:63]}  core-x86_64-unknown-linux-gnu",
    ],
    ids=["bad-digest", "single-space", "no-name", "short-digest"],
)
def test_rejects_a_malformed_line(line: str) -> None:
    """A line that is not sha256sum format is an error, never a skipped row."""
    with pytest.raises(ChecksumError):
        parse_checksums(f"{line}\n")


def test_rejects_an_asset_listed_twice_with_conflicting_digests() -> None:
    """Two digests for one name means the aggregate cannot pin that asset."""
    text = (
        f"{DIGEST_A}  core-x86_64-unknown-linux-gnu\n"
        f"{DIGEST_B}  core-x86_64-unknown-linux-gnu\n"
    )

    with pytest.raises(ChecksumError, match="twice"):
        parse_checksums(text)


def test_rejects_an_empty_aggregate() -> None:
    """No checksums means no release to point at."""
    with pytest.raises(ChecksumError, match="empty"):
        parse_checksums("\n\n")


def test_require_refuses_to_invent_a_missing_digest() -> None:
    """The no-fallback rule: an unattached asset cannot be pinned."""
    with pytest.raises(ChecksumError, match="no entry for"):
        require({"core-x86_64-unknown-linux-gnu": DIGEST_A}, "mcp-aarch64-apple-darwin")


def test_read_checksums_sees_real_bytes_not_translated_ones(tmp_path: Path) -> None:
    """Reading opts out of newline translation, so CRLF still fails on Windows.

    With the default text mode this read would silently normalise CRLF to LF
    and report a clean aggregate on the one platform that produces the defect.
    """
    path = tmp_path / "SHA256SUMS"
    path.write_bytes(f"{DIGEST_A}  core-x86_64-pc-windows-msvc.exe\r\n".encode())

    with pytest.raises(ChecksumError, match="carriage return"):
        read_checksums(path)
