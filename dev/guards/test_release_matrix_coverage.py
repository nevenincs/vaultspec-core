"""Contracts binding the release build matrix to the matrices that exercise it.

A target is BUILT by ``binaries.yml``'s ``build`` job, RUN WITH NO NETWORK by
its ``offline`` job, and RUN FROM THE PUBLISHED RELEASE by ``acquisition.yml``.
The three lists are separate matrices in two files, and GitHub has no way to
share one matrix between two jobs, so each has to be kept in step with the
others by hand. This repository has already shipped two defects whose whole
cause was exactly that - the preflight's hand-kept runner selectors, and the
release's hand-kept target expectations - and both were fixed by deriving one
list from another.

These two cannot be derived, so they are asserted.

*Offline coverage.* A target in ``build`` and absent from ``offline`` has its
artifact uploaded as ``unverified-*`` and never renamed, so the release
silently loses that platform. A target in ``offline`` and absent from ``build``
fails its download and reds the release for nothing.

*Acquisition coverage.* A published binary nobody executes is an untested
binary, and the acquisition check is the only thing that starts a release bundle
on a machine with no checkout and no toolchain. v0.1.71 attached
``vaultspec-core-aarch64-unknown-linux-gnu`` while the acquisition matrix still
fetched only the x86_64 file; the release guards stayed green because they
assert the asset EXISTS, not that anything ran it.

Both were inline shell in a CI job, where they ran once per pull request on one
runner and could not be run at all on a laptop. They read two committed files
and compare lists, which is a repository fact, so they belong in the ``repo``
lane with the rest of the workflow contracts - and they parse the workflows as
YAML rather than with ``awk`` over indentation, which is what let the previous
version need a hand-written job-boundary walker to tell two ``target:`` keys
apart.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
import yaml

pytestmark = [pytest.mark.repo]

#: Repository root (``dev/guards/`` -> ``dev/`` -> repo).
ROOT = Path(__file__).resolve().parents[2]

#: Workflow directory, relative to the repository root.
WORKFLOWS = ROOT / ".github" / "workflows"

#: The suffix identifying a Linux target triple. Acquisition covers macOS and
#: Windows in jobs of their own, but the build and acquisition matrices still
#: use the same target key for every bundle.
LINUX_SUFFIX = "-linux-gnu"


def _matrix_values(workflow: str, job: str, key: str) -> set[str]:
    """Return every ``key`` named by ``job``'s matrix ``include`` entries.

    Asserts the list is non-empty. A derivation that yields nothing passes
    every comparison it feeds without asserting anything, and the way it comes
    to yield nothing is a job being renamed - precisely when these contracts
    most need to fail.
    """
    path = WORKFLOWS / workflow
    document = cast("dict[str, Any]", yaml.safe_load(path.read_text(encoding="utf-8")))
    jobs = document["jobs"]
    assert job in jobs, (
        f"{workflow} has no `{job}` job; it was renamed or removed, and the "
        "coverage this derives cannot be checked"
    )
    include = jobs[job].get("strategy", {}).get("matrix", {}).get("include", [])
    values = {entry[key] for entry in include if key in entry}
    assert values, (
        f"no `{key}:` entries in {workflow}'s `{job}` matrix; the matrix shape "
        "moved and this assertion would otherwise pass vacuously"
    )
    return values


def test_every_built_target_is_gated_offline() -> None:
    """The build matrix and the offline gate cover the same targets.

    Every target that is built must be run with the network taken away before
    it can become a release asset.
    """
    built = _matrix_values("binaries.yml", "build", "target")
    gated = _matrix_values("binaries.yml", "offline", "target")
    assert built == gated, (
        "the build matrix and the offline gate cover different targets. "
        f"Built but not gated: {sorted(built - gated)}. "
        f"Gated but not built: {sorted(gated - built)}."
    )


def test_every_built_linux_target_is_acquired() -> None:
    """Every Linux target that is built is also fetched and run as a user would."""
    built = {
        target
        for target in _matrix_values("binaries.yml", "build", "target")
        if target.endswith(LINUX_SUFFIX)
    }
    assert built, (
        "no Linux targets in the build matrix; the acquisition-coverage "
        "assertion cannot run"
    )
    acquired = _matrix_values("acquisition.yml", "acquire", "target")
    missing = built - acquired
    assert not missing, (
        f"acquisition.yml fetches no bundle for: {sorted(missing)}. A target "
        "that is built and published must also be executed from the published "
        "release, on a machine with no checkout and no toolchain."
    )


def test_linux_offline_gate_runs_the_extracted_bundle() -> None:
    """The no-network gate executes extracted stable names, not archive files."""
    workflow = (WORKFLOWS / "binaries.yml").read_text(encoding="utf-8")
    assert '"${PWD}/offline-bundle:/artifacts:ro"' in workflow
    assert 'ARTIFACTS="${PWD}/offline-bundle"' in workflow
    assert '"${ARTIFACTS}"/vaultspec-core --version' in workflow


def test_release_holds_latest_until_target_bundles_are_complete() -> None:
    """The release state is held and the completeness gate precedes upload."""
    workflow = (WORKFLOWS / "binaries.yml").read_text(encoding="utf-8")
    hold = workflow.index("name: Hold release out of latest during validation")
    complete = workflow.index("name: Assert every declared target attached")
    upload = workflow.index("name: Upload to release")
    assert hold < upload
    assert complete < upload
    verification = workflow.index("verify-release-assets:")
    assert "runs-on: ubuntu-latest" in workflow[verification:]
