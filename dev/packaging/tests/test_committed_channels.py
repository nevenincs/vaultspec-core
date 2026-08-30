"""Guards on how the release job produces channel pointers.

This module used to assert on ``bucket/vaultspec-core.json`` and
``Formula/vaultspec-core.rb`` in this repository. Those files are gone: a
channel root is per-account rather than per-product, so the pointers a user
installs live in ``nevenincs/homebrew-tap`` and the release job generates
straight into a checkout of it.

The assertions did not survive the move unchanged, and the reason is worth
recording. They had already stopped guarding anything: the release job wrote to
the tap while these tests read the in-repo copies, so the committed files went
four releases stale while the suite stayed green. A test decoupled from what it
protects is worse than an absent one, because its green is read as evidence.

They now live in two better places. The digest and consistency checks moved into
``dev/packaging/validate.py``, which the release job runs against the real
generated pointers between writing and committing them - earlier in time and
against the files that actually ship. What remains here is the assertion that
cannot move, because its subject is this repository: the shape of the release
job itself.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.repo


def test_the_release_workflow_generates_rather_than_edits_the_pointers(
    repo_root: Path,
) -> None:
    """The channels are produced by the generator, not rewritten by shell.

    The inline ``jq``/``awk`` bump this replaced could write a manifest with
    empty hashes out of a green run - which is exactly what
    vaultspec-core-v0.1.60 shipped. Pinning the invocation keeps the release
    path from drifting back to editing a pointer in place.
    """
    workflow = (repo_root / ".github" / "workflows" / "binaries.yml").read_text(
        encoding="utf-8",
    )

    assert "dev.packaging.generate" in workflow
    assert "--checksums dist-bin/SHA256SUMS" in workflow
    assert "jq \\" not in workflow


def test_the_release_workflow_validates_before_committing(repo_root: Path) -> None:
    """Generation is not enough on its own; the result must be checked.

    The 0.1.60 manifest was *generated* and still uninstallable. The validator
    is what turns that from a release that ships to a release that stops, so
    the release job losing this step would silently restore the old failure
    mode - with the reassuring `generate` invocation above still in place.
    """
    workflow = (repo_root / ".github" / "workflows" / "binaries.yml").read_text(
        encoding="utf-8",
    )

    assert "dev.packaging.validate" in workflow, (
        "the release job no longer validates the pointers it generates"
    )
    assert workflow.index("dev.packaging.generate") < workflow.index(
        "dev.packaging.validate",
    ), "validation must run after generation, not before"


def test_this_repository_carries_no_second_channel_root(repo_root: Path) -> None:
    """No ``bucket/`` or ``Formula/`` here. One product must have one root.

    Two roots for one product is not a tidiness problem: while both existed,
    every install instruction in the README named the stale one, so anyone who
    followed the documented path was pinned to 0.1.61 permanently and silently
    while the live tap moved on to 0.1.65.
    """
    for stale in ("bucket", "Formula"):
        assert not (repo_root / stale).exists(), (
            f"{stale}/ is back. Channel pointers belong in nevenincs/homebrew-tap; "
            f"see docs/channels.md."
        )
