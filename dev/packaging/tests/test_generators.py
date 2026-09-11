"""Guards for the Scoop manifest and Homebrew formula generators.

The contracts asserted here are the ones a package manager enforces at
install time on a user's machine, where a mistake is a failed install rather
than a failed build: the manifest names assets the release actually attached,
every pinned digest is the release's own, an unbuilt platform is absent
rather than invented, and a pointer never moves backward.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

import pytest

from dev.packaging import homebrew, products, scoop
from dev.packaging.checksums import ChecksumError
from dev.packaging.generate import available_targets, generate
from dev.packaging.pointer import PointerError, check_forward
from dev.packaging.products import VAULTSPEC_CORE

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.unit

VERSION = "0.1.60"
TAG = f"vaultspec-core-v{VERSION}"

#: Every triple the release matrix attaches, plus the two Homebrew serves
#: that it does not, so coverage gaps are exercised rather than assumed.
ALL_TARGETS = (
    products.WINDOWS_X86_64,
    products.MACOS_ARM64,
    products.MACOS_X86_64,
    products.LINUX_X86_64,
)


def digests_for(targets: tuple[str, ...] = ALL_TARGETS) -> dict[str, str]:
    """Return a synthetic but well-formed digest map for the given triples."""
    return {
        VAULTSPEC_CORE.bundle_name(VERSION, target): f"{index:064x}"
        for index, target in enumerate(targets)
    }


def write_aggregate(path: Path, digests: dict[str, str]) -> Path:
    """Write a ``SHA256SUMS`` file for the given digest map."""
    body = "".join(f"{digest}  {name}\n" for name, digest in digests.items())
    path.write_text(body, encoding="utf-8", newline="")
    return path


def test_generator_bundle_names_are_target_specific_and_stable() -> None:
    """The channel names the one public bundle each target receives.

    The extracted commands are stable; only the outer archive carries the
    target-specific identity needed to select a platform download.
    """
    for target in ALL_TARGETS:
        assert VAULTSPEC_CORE.bundle_name(VERSION, target).endswith(
            products.archive_suffix(target)
        )
        assert all(
            VAULTSPEC_CORE.executable_name(executable, target)
            == executable.name + (".exe" if target == products.WINDOWS_X86_64 else "")
            for executable in VAULTSPEC_CORE.executables
        )


def test_scoop_manifest_pins_the_release_digests() -> None:
    """Every hash in the manifest comes from the aggregate, in URL order."""
    digests = digests_for()

    manifest = scoop.render_manifest(VAULTSPEC_CORE, VERSION, digests)

    # The manifest is a JSON document, so its values are `object`. Narrow
    # explicitly rather than letting the element types stay unknown: the
    # assertion below is about the pairing of URLs to digests, and a silently
    # unknown element type would let that pairing be checked as `object`.
    urls = cast("list[str]", manifest["url"])
    hashes = cast("list[str]", manifest["hash"])
    assert len(urls) == len(hashes) == 1
    for url, digest in zip(urls, hashes, strict=True):
        assert digest == digests[url.rsplit("/", 1)[-1]]
    assert manifest["bin"] == [
        ["vaultspec-core.exe", "vaultspec-core"],
        ["vaultspec-mcp.exe", "vaultspec-mcp"],
    ]


def test_scoop_manifest_never_emits_an_empty_hash() -> None:
    """The 0.1.60 failure mode, asserted directly.

    A missing digest must raise where it is looked up, not survive into a
    committed manifest that Scoop will refuse on the user's machine.
    """
    incomplete = digests_for()
    del incomplete[VAULTSPEC_CORE.bundle_name(VERSION, products.WINDOWS_X86_64)]

    with pytest.raises(ChecksumError, match="no entry for"):
        scoop.render_manifest(VAULTSPEC_CORE, VERSION, incomplete)


def test_scoop_manifest_is_valid_json_scoop_can_read() -> None:
    """The committed bytes round-trip, and name the version being installed."""
    rendered = scoop.render(VAULTSPEC_CORE, VERSION, digests_for())

    assert rendered.endswith("\n")
    assert json.loads(rendered)["version"] == VERSION


def test_homebrew_formula_pins_every_covered_platform() -> None:
    """Each built platform gets one bundle url and digest."""
    digests = digests_for()

    formula = homebrew.render(
        VAULTSPEC_CORE,
        VERSION,
        digests,
        (products.MACOS_ARM64, products.MACOS_X86_64, products.LINUX_X86_64),
    )

    for target in (products.MACOS_ARM64, products.MACOS_X86_64, products.LINUX_X86_64):
        asset = VAULTSPEC_CORE.bundle_name(VERSION, target)
        assert f"/{asset}" in formula
        assert f'sha256 "{digests[asset]}"' in formula


def test_homebrew_formula_omits_an_unbuilt_platform() -> None:
    """A gap in the build matrix is absent from the formula, not faked.

    Homebrew then reports an unsupported platform, which is true, instead of
    failing a checksum against an asset that was never published.
    """
    formula = homebrew.render(
        VAULTSPEC_CORE,
        VERSION,
        digests_for(),
        (products.MACOS_ARM64, products.MACOS_X86_64, products.LINUX_X86_64),
    )

    assert products.LINUX_ARM64 not in formula
    assert "on_linux do" in formula


def test_homebrew_formula_declares_the_expected_ruby_surface() -> None:
    """The formula names its class, version, licence, and both executables."""
    formula = homebrew.render(
        VAULTSPEC_CORE,
        VERSION,
        digests_for(),
        (products.MACOS_ARM64, products.MACOS_X86_64, products.LINUX_X86_64),
    )

    assert formula.startswith("class VaultspecCore < Formula\n")
    assert f'version "{VERSION}"' in formula
    assert 'license "MIT"' in formula
    assert 'bin.install "vaultspec-core"' in formula
    assert 'bin.install "vaultspec-mcp"' in formula
    assert 'resource("vaultspec-mcp")' not in formula
    assert formula.endswith("end\n")


def test_available_targets_requires_a_complete_bundle_on_a_platform() -> None:
    """A missing target bundle is not coverage."""
    digests = digests_for()
    del digests[VAULTSPEC_CORE.bundle_name(VERSION, products.MACOS_ARM64)]

    assert products.MACOS_ARM64 not in available_targets(
        VAULTSPEC_CORE, VERSION, digests
    )
    assert products.MACOS_X86_64 in available_targets(VAULTSPEC_CORE, VERSION, digests)


@pytest.mark.parametrize(
    ("current", "incoming"),
    [("0.1.60", "0.1.59"), ("0.2.0", "0.1.99"), ("1.0.0", "0.9.9")],
)
def test_pointer_guard_refuses_a_backward_bump(current: str, incoming: str) -> None:
    """A stale re-run must not un-publish the current release."""
    with pytest.raises(PointerError, match="backward"):
        check_forward(current, incoming)


@pytest.mark.parametrize(
    ("current", "incoming"),
    [(None, "0.1.60"), ("0.1.60", "0.1.60"), ("0.1.59", "0.1.60")],
    ids=["first-publication", "converging-rerun", "forward"],
)
def test_pointer_guard_allows_first_equal_and_forward(
    current: str | None,
    incoming: str,
) -> None:
    """Publishing anew, converging a partial release, and bumping all pass."""
    check_forward(current, incoming)


def test_generate_writes_both_channels_and_guards_the_second_run(
    tmp_path: Path,
) -> None:
    """One invocation produces both pointers; an older tag is then refused."""
    aggregate = write_aggregate(tmp_path / "SHA256SUMS", digests_for())

    written = generate(tmp_path, VAULTSPEC_CORE, TAG, aggregate)

    assert [path.name for path in written] == [
        "vaultspec-core.json",
        "vaultspec-core.rb",
    ]
    assert json.loads(written[0].read_text(encoding="utf-8"))["version"] == VERSION

    with pytest.raises(PointerError, match="backward"):
        generate(tmp_path, VAULTSPEC_CORE, "vaultspec-core-v0.1.59", aggregate)


def test_generate_writes_lf_line_endings(tmp_path: Path) -> None:
    """Committed channel files are LF on every host that generates them."""
    aggregate = write_aggregate(tmp_path / "SHA256SUMS", digests_for())

    for path in generate(tmp_path, VAULTSPEC_CORE, TAG, aggregate):
        assert b"\r" not in path.read_bytes()
