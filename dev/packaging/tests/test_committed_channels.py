"""Guards on the channel pointers actually committed to this repository.

The generators are unit-tested against synthetic input elsewhere. These
assertions are about the real files a user's package manager will read from
this checkout, and they are the ones that would have caught
vaultspec-core-v0.1.60 shipping a Scoop manifest with empty hashes: the
release job was green, the unit tests were green, and nothing looked at what
had been committed.

They are offline by construction. Verifying a digest against the release
would need the network, so what is checked here is internal consistency -
well-formed digests, agreement between the two channels, and agreement with
the asset names the build matrix produces.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

import pytest

from dev.binaries.build_pyapp import BINARIES, asset_name
from dev.packaging import products
from dev.packaging.generate import formula_path, scoop_path
from dev.packaging.pointer import existing_homebrew_version, existing_scoop_version
from dev.packaging.products import VAULTSPEC_CORE

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.repo

SHA256 = re.compile(r"^[0-9a-f]{64}$")


def test_the_committed_scoop_manifest_pins_real_digests(repo_root: Path) -> None:
    """Every hash is 64 hex characters - never blank, never a placeholder.

    This is the direct guard on the 0.1.60 failure: the manifest carried the
    released version and correct URLs alongside ``"hash": ["", ""]``, which
    Scoop cannot install.
    """
    manifest = json.loads(
        scoop_path(repo_root, VAULTSPEC_CORE).read_text(encoding="utf-8"),
    )

    assert manifest["hash"], "manifest pins no hashes"
    assert len(manifest["hash"]) == len(manifest["url"])
    for digest in manifest["hash"]:
        assert SHA256.match(digest), f"not a sha256 digest: {digest!r}"


def test_the_committed_formula_pins_real_digests(repo_root: Path) -> None:
    """The formula's every ``sha256`` is a real digest, on every platform."""
    formula = formula_path(repo_root, VAULTSPEC_CORE).read_text(encoding="utf-8")

    digests = re.findall(r'sha256 "([^"]*)"', formula)
    assert digests, "formula pins no digests"
    for digest in digests:
        assert SHA256.match(digest), f"not a sha256 digest: {digest!r}"


def test_both_channels_point_at_the_same_release(repo_root: Path) -> None:
    """Scoop and Homebrew must not disagree about what the current release is.

    They are generated together from one aggregate, so a divergence means one
    of them was hand-edited or a generation half-failed.
    """
    scoop_version = existing_scoop_version(scoop_path(repo_root, VAULTSPEC_CORE))
    brew_version = existing_homebrew_version(formula_path(repo_root, VAULTSPEC_CORE))

    assert scoop_version is not None
    assert scoop_version == brew_version


def test_committed_channels_name_assets_the_build_matrix_produces(
    repo_root: Path,
) -> None:
    """Every asset a channel points at is one the builder is able to emit."""
    manifest = json.loads(
        scoop_path(repo_root, VAULTSPEC_CORE).read_text(encoding="utf-8"),
    )
    formula = formula_path(repo_root, VAULTSPEC_CORE).read_text(encoding="utf-8")
    referenced = {str(url).rsplit("/", 1)[-1] for url in manifest["url"]}
    referenced |= set(re.findall(r'url "[^"]*/([^"/]+)"', formula))

    buildable = {
        asset_name(binary, target)
        for binary in BINARIES
        for target in (
            products.WINDOWS_X86_64,
            products.MACOS_ARM64,
            products.MACOS_X86_64,
            products.LINUX_X86_64,
            products.LINUX_ARM64,
        )
    }
    assert referenced <= buildable, (
        f"unbuildable assets: {sorted(referenced - buildable)}"
    )


def test_the_release_workflow_generates_rather_than_edits_the_pointers(
    repo_root: Path,
) -> None:
    """The channels are produced by the generator, not rewritten by shell.

    The inline ``jq``/``awk`` bump this replaced could write a manifest with
    empty hashes out of a green run; pinning the invocation keeps the release
    path from drifting back to editing a pointer in place.
    """
    workflow = (repo_root / ".github" / "workflows" / "binaries.yml").read_text(
        encoding="utf-8",
    )

    assert "dev.packaging.generate" in workflow
    assert "--checksums dist-bin/SHA256SUMS" in workflow
    assert "jq \\" not in workflow
