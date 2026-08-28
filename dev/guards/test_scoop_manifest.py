"""The committed scoop manifest is an integrity boundary, not a download list.

``scoop install`` reads the ``url``/``hash`` pair committed here - not the
``checkver``/``autoupdate`` stanzas, which only serve maintainer tooling. So a
manifest that carries an empty hash does not merely lack a nicety: it installs
tens of megabytes of executables with no integrity check, from a URL anyone who
can publish a release asset controls.

The manifest is rewritten by the scoop-bump step in ``binaries.yml``. These
guards assert the properties that step must preserve, so a bump that silently
produces a hashless or misaligned manifest fails here rather than in a user's
shell.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

pytestmark = [pytest.mark.repo]

#: Repository root (``dev/guards/`` -> ``dev/`` -> repo).
ROOT = Path(__file__).resolve().parents[2]

MANIFEST = ROOT / "bucket" / "vaultspec-core.json"

#: A scoop ``hash`` entry with no algorithm prefix is a bare SHA-256 hex digest.
SHA256_HEX = re.compile(r"\A[0-9a-f]{64}\Z")


@pytest.fixture(scope="module")
def manifest() -> dict[str, Any]:
    """Return the committed scoop manifest."""
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_every_url_carries_a_real_digest(manifest: dict[str, Any]) -> None:
    """An empty or short hash is an install with no integrity check at all.

    This is the regression that shipped: the bump step derived the Windows
    digests from a ``SHA256SUMS`` whose Windows lines ended in CRLF, matched
    nothing, and committed ``["", ""]``.
    """
    hashes: list[str] = manifest["hash"]
    assert hashes, "manifest declares no hashes"
    for index, digest in enumerate(hashes):
        assert SHA256_HEX.fullmatch(digest), (
            f"hash[{index}] is not a sha256 hex digest: {digest!r}"
        )


def test_each_url_is_paired_with_exactly_one_hash(manifest: dict[str, Any]) -> None:
    """Scoop pairs the arrays positionally; a length skew mismatches assets."""
    assert len(manifest["hash"]) == len(manifest["url"])


def test_every_url_points_at_the_manifests_own_version(
    manifest: dict[str, Any],
) -> None:
    """A url left on the previous tag serves old bytes under a new version."""
    version: str = manifest["version"]
    urls: list[str] = manifest["url"]
    for url in urls:
        assert f"/vaultspec-core-v{version}/" in url, url


def test_every_declared_bin_is_downloaded_by_a_url(manifest: dict[str, Any]) -> None:
    """A ``bin`` entry with no matching download shims a file scoop never wrote."""
    urls: list[str] = manifest["url"]
    downloaded = {url.rsplit("/", 1)[-1] for url in urls}
    # A scoop ``bin`` entry is either a bare filename or ``[filename, alias]``.
    entries: list[str | list[str]] = manifest["bin"]
    for entry in entries:
        filename = entry[0] if isinstance(entry, list) else entry
        assert filename in downloaded, f"{filename} is shimmed but never downloaded"


def test_downloads_are_served_over_https(manifest: dict[str, Any]) -> None:
    """The digest is the only integrity check; the transport must not be plain."""
    urls: list[str] = manifest["url"]
    for url in urls:
        assert url.startswith("https://"), url
