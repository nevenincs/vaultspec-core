"""A reused workspace must be indistinguishable from a freshly built one.

The suite provisions hundreds of identical workspaces per run, so it builds each
shape once and copies it. That is only sound while a copy is genuinely
equivalent to the real thing, and there are two ways for it to stop being so.

The first is a tree that records where it lives. ``.vaultspec/mcp-ownership.json``
stores the absolute path of every provider config it manages, so an unrebased
copy claims ownership of the TEMPLATE's files: a test asserting on ownership
would pass while describing a directory it has never heard of. That is the worst
possible failure - green, and about the wrong thing - so it is checked directly
rather than trusted to review.

The second is the reuse widening. ``install()`` serves a copy only for the
default shape into an empty directory; every other shape has to run the product,
because the product's behaviour on a non-empty or non-default target is
frequently what is under test.

These tests are the counterweight to the performance work: they are what make
"identical" a checked claim rather than an assumption.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vaultspec_core.core.enums import DirName
from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]


def _relative_tree(root: Path) -> set[str]:
    """Return every path under *root*, relative and separator-normalised."""
    return {
        entry.relative_to(root).as_posix()
        for entry in root.rglob("*")
        if not entry.is_dir()
    }


class TestACopiedWorkspaceMatchesABuiltOne:
    """The reuse must not be observable from inside a test."""

    def test_the_same_files_are_present(self, tmp_path: Path) -> None:
        copied = WorkspaceFactory(tmp_path / "copied").install().path
        # `force` is not the default shape, so this one runs the real install.
        built = WorkspaceFactory(tmp_path / "built").install(force=True).path

        assert _relative_tree(copied) == _relative_tree(built)

    def test_no_file_still_points_at_the_template(self, tmp_path: Path) -> None:
        workspace = WorkspaceFactory(tmp_path / "workspace").install().path

        offenders: list[str] = []
        for entry in workspace.rglob("*"):
            if not entry.is_file():
                continue
            try:
                text = entry.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            # Every path this workspace records must be inside it. The template
            # lives elsewhere, so its name appearing here means a stale
            # reference survived the copy.
            if "vsc-install-template-" in text or "workspace-templates" in text:
                offenders.append(entry.relative_to(workspace).as_posix())

        assert not offenders, (
            "A copied workspace still references the template it came from. "
            "Anything asserting on these paths would pass while describing "
            "another directory.\n  " + "\n  ".join(offenders)
        )

    def test_the_ownership_record_names_this_workspace(self, tmp_path: Path) -> None:
        workspace = WorkspaceFactory(tmp_path / "workspace").install().path
        ownership = workspace / DirName.VAULTSPEC / "mcp-ownership.json"

        assert ownership.is_file(), "install did not write an ownership record"
        recorded = ownership.read_text(encoding="utf-8")
        assert (
            str(workspace) in recorded
            or str(workspace).replace("\\", "\\\\") in recorded
        ), (
            "The ownership record does not name the workspace it belongs to, so "
            "the rebase after a template copy is not doing its job."
        )


class TestTheReuseStaysNarrow:
    """Only the shape that is provably identical may be served from a copy."""

    def test_a_seeded_directory_runs_the_real_install(self, tmp_path: Path) -> None:
        """`create_gitignore().install()` must exercise the product.

        This is the pattern GH issue 399 turned on: the block writer's
        behaviour against a pre-existing .gitignore is the thing under test, and
        serving a copy would replace it with a file the product never saw.
        """
        factory = WorkspaceFactory(tmp_path / "workspace")
        factory.root.mkdir(parents=True)
        factory.create_gitignore("# authored by the user\n")
        factory.install()

        gitignore = (factory.path / ".gitignore").read_text(encoding="utf-8")
        assert "# authored by the user" in gitignore, (
            "A pre-existing .gitignore was replaced rather than appended to, "
            "which means the template copy served a call it should not have."
        )

    def test_each_provider_gets_its_own_template(self, tmp_path: Path) -> None:
        """Shapes must not bleed into each other through a shared cache.

        The templates are keyed by (provider, mode); a key collision would hand
        a single-provider install the all-provider tree, and every assertion
        about what an install does NOT create would silently invert.
        """
        workspace = WorkspaceFactory(tmp_path / "workspace").install("claude").path

        assert (workspace / DirName.CLAUDE).is_dir()
        assert not (workspace / DirName.GEMINI).exists(), (
            "A single-provider install produced another provider's directory, "
            "so it was served from the wrong template."
        )

    def test_an_upgrade_runs_the_real_install(self, tmp_path: Path) -> None:
        """An upgrade reconciles what is on disk, so it can never be a copy."""
        factory = WorkspaceFactory(tmp_path / "workspace")
        factory.install()
        marker = factory.path / ".vaultspec" / "rules" / "user-authored.md"
        marker.write_text("# authored\n", encoding="utf-8")

        factory.install(upgrade=True)

        assert marker.is_file(), (
            "An upgrade replaced the workspace wholesale, which means it was "
            "served from a template instead of reconciling what was there."
        )
