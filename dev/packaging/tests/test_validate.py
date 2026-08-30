"""The channel-pointer validator, exercised on real generator output.

The fixtures here are not hand-written manifests. Each test generates a real
pointer pair with the real generator, then breaks exactly one invariant, so a
change to the rendering that silently stops satisfying an assertion shows up
here rather than at install time.

That distinction matters for this particular guard: the failure it exists to
catch (vaultspec-core-v0.1.60) was a manifest that looked entirely correct
except for two empty strings.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from dev.binaries.build_pyapp import BINARIES, asset_name
from dev.packaging import products
from dev.packaging.generate import formula_path, generate, scoop_path
from dev.packaging.products import VAULTSPEC_CORE
from dev.packaging.validate import REPO_ROOT, buildable_targets, validate

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.unit

TAG = "vaultspec-core-v9.9.9"
_DIGEST = "a" * 64


@pytest.fixture
def channel_root(tmp_path: Path) -> Path:
    """A generated, well-formed pair of channel pointers in a scratch root.

    The checksums cover exactly the targets THE MATRIX BUILDS, because that is
    what a real ``SHA256SUMS`` contains - the release aggregates the assets that
    were produced, not the ones the products module can name.

    The first cut of this fixture listed every Homebrew target the product
    serves, which fabricated digests for `aarch64-unknown-linux-gnu` - a leg
    #356 removed. The validator flagged the resulting pointer, correctly, and
    the fixture was what was wrong. Deriving here keeps the fixture honest and
    keeps these tests from restating whichever legs main happens to carry.
    """
    built = set(buildable_targets(REPO_ROOT))
    lines = [
        f"{_DIGEST}  {asset_name(binary, target)}"
        for target in (*products.HOMEBREW_TARGETS, products.WINDOWS_X86_64)
        if VAULTSPEC_CORE.serves(target) and target in built
        for binary in BINARIES
    ]
    assert lines, "the matrix builds nothing this product serves"
    checksums = tmp_path / "SHA256SUMS"
    # newline="" so Windows does not translate to CRLF: the checksum reader
    # rejects a carriage return outright, which is correct and which this
    # fixture tripped over on the first run.
    checksums.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")

    root = tmp_path / "tap"
    root.mkdir()
    generate(tag=TAG, checksums=checksums, product=VAULTSPEC_CORE, root=root)
    return root


def test_generated_pointers_validate_clean(channel_root: Path) -> None:
    """The generator's own output is publishable. Everything else is a delta."""
    assert validate(channel_root, VAULTSPEC_CORE) == []


def test_blank_scoop_hashes_are_refused(channel_root: Path) -> None:
    """The vaultspec-core-v0.1.60 failure, reproduced exactly.

    The manifest keeps its correct version and URLs; only the digests are
    emptied. Scoop cannot install this, and the release that shipped it was
    green from end to end.
    """
    path = scoop_path(channel_root, VAULTSPEC_CORE)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["hash"] = [""] * len(manifest["hash"])
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    problems = validate(channel_root, VAULTSPEC_CORE)
    assert problems
    assert all("not a sha256 digest" in problem for problem in problems)


def test_a_truncated_digest_is_refused(channel_root: Path) -> None:
    """Not merely non-empty - a digest must be a full sha256."""
    path = scoop_path(channel_root, VAULTSPEC_CORE)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["hash"][0] = _DIGEST[:32]
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    assert any(
        "not a sha256 digest" in problem
        for problem in validate(channel_root, VAULTSPEC_CORE)
    )


def test_a_blank_formula_digest_is_refused(channel_root: Path) -> None:
    """The Homebrew side of the same failure."""
    path = formula_path(channel_root, VAULTSPEC_CORE)
    path.write_text(
        path.read_text(encoding="utf-8").replace(f'sha256 "{_DIGEST}"', 'sha256 ""', 1),
        encoding="utf-8",
    )

    assert any(
        "not a sha256 digest" in problem
        for problem in validate(channel_root, VAULTSPEC_CORE)
    )


def test_channels_disagreeing_about_the_version_are_refused(
    channel_root: Path,
) -> None:
    """Both are generated from one aggregate, so a divergence is a half-failure."""
    path = formula_path(channel_root, VAULTSPEC_CORE)
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            'version "9.9.9"', 'version "9.9.8"', 1
        ),
        encoding="utf-8",
    )

    assert any(
        "channels disagree" in problem
        for problem in validate(channel_root, VAULTSPEC_CORE)
    )


def test_an_asset_no_build_produces_is_refused(channel_root: Path) -> None:
    """A pointer at a nonexistent asset is a 404 at install time and nowhere else.

    This is the shape vaultspec-dashboard's winget manifests still carry: a URL
    for an installer no release has ever attached.
    """
    path = scoop_path(channel_root, VAULTSPEC_CORE)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["url"][0] = (
        "https://github.com/nevenincs/vaultspec-core/releases/download/"
        f"{TAG}/vaultspec-core-0.1.2-x86_64-pc-windows-msvc.msi"
    )
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    assert any(
        "names an asset no build produces" in problem
        for problem in validate(channel_root, VAULTSPEC_CORE)
    )


def test_a_missing_pointer_is_refused_rather_than_passing_vacuously(
    tmp_path: Path,
) -> None:
    """An empty root must fail. A validator that passes on nothing guards nothing."""
    problems = validate(tmp_path, VAULTSPEC_CORE)
    assert problems
    assert all("does not exist" in problem for problem in problems)


def _repo_with_matrix(tmp_path: Path, *targets: str) -> Path:
    """A stand-in repository whose build matrix declares exactly ``targets``."""
    repo = tmp_path / "repo"
    workflow = repo / ".github" / "workflows"
    workflow.mkdir(parents=True)
    rows = "\n".join(
        f"          - name: leg-{i}\n            target: {target}"
        for i, target in enumerate(targets)
    )
    (workflow / "binaries.yml").write_text(
        f"jobs:\n  build:\n    strategy:\n      matrix:\n        include:\n{rows}\n",
        encoding="utf-8",
        newline="",
    )
    return repo


def test_buildable_targets_reads_the_matrix(tmp_path: Path) -> None:
    """The buildable set comes from the matrix, not from a second list."""
    repo = _repo_with_matrix(tmp_path, "b-triple", "a-triple", "a-triple")
    assert buildable_targets(repo) == ("a-triple", "b-triple")


def test_an_asset_for_a_target_the_matrix_dropped_is_refused(
    channel_root: Path, tmp_path: Path
) -> None:
    """The defect this check was carrying, made into a test.

    The buildable set used to be a hand-written list of all five triples the
    products module knows. The matrix builds fewer, so a pointer naming a
    dropped target validated clean - and the dropped target is precisely the
    one a release withdraws because its binary does not run. The check would
    have approved the artifact the repository was in the middle of removing.

    Asserted against a synthetic matrix rather than this repository's, so the
    test states the property instead of restating whichever legs main happens
    to carry today.
    """
    dropped = products.MACOS_X86_64
    repo = _repo_with_matrix(tmp_path, products.WINDOWS_X86_64, products.LINUX_X86_64)

    path = scoop_path(channel_root, VAULTSPEC_CORE)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["url"][0] = (
        f"https://github.com/nevenincs/vaultspec-core/releases/download/{TAG}/"
        f"{asset_name(BINARIES[0], dropped)}"
    )
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    problems = validate(channel_root, VAULTSPEC_CORE, repo_root=repo)
    assert any("names an asset no build produces" in problem for problem in problems)


def test_an_unreadable_matrix_is_reported_rather_than_assumed(
    channel_root: Path, tmp_path: Path
) -> None:
    """No matrix means the question cannot be answered - so it must not be.

    Guessing in either direction is how a check starts lying: assume everything
    is buildable and it approves anything; assume nothing is and it rejects a
    correct release.
    """
    problems = validate(channel_root, VAULTSPEC_CORE, repo_root=tmp_path / "absent")
    assert any(
        "cannot determine what this repository builds" in problem
        for problem in problems
    )
