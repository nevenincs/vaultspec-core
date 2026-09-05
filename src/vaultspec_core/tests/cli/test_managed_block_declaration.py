"""Tests for the committed managed-block declaration.

Declining a managed git block used to be recorded only in
``.vaultspec/providers.json``, which is per-machine and is itself listed inside
the very block whose removal it records. The decision could not reach a
teammate: they cloned, installed, and the install cleared the flag and wrote
the block back.

These tests run the sequence that failed, against the real filesystem and a
real ``git`` subprocess, plus the schema and verb behaviour underneath it.
"""

from __future__ import annotations

import os
import subprocess
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.core.exceptions import VaultSpecError
from vaultspec_core.core.git_artifacts import block_management_enabled
from vaultspec_core.core.manifest import read_manifest_data, write_manifest_data
from vaultspec_core.core.workspace_mode import (
    BlocksDeclaration,
    HooksDeclaration,
    read_blocks_declaration,
    read_hooks_declaration,
    write_blocks_declaration,
    write_hooks_declaration,
)
from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory

if TYPE_CHECKING:
    from pathlib import Path

MARKER = "vaultspec-managed"


def _run_git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Invoke ``git`` in *cwd* with a deterministic identity and no host config."""
    null = "NUL" if os.name == "nt" else "/dev/null"
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "vaultspec-test",
        "GIT_AUTHOR_EMAIL": "test@vaultspec.local",
        "GIT_COMMITTER_NAME": "vaultspec-test",
        "GIT_COMMITTER_EMAIL": "test@vaultspec.local",
        "GIT_CONFIG_GLOBAL": null,
        "GIT_CONFIG_SYSTEM": null,
        "HOME": str(cwd),
    }
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def _strip_block(path: Path) -> None:
    """Remove the managed block from *path*, the way an operator would."""
    lines = path.read_text(encoding="utf-8").splitlines()
    kept: list[str] = []
    inside = False
    for line in lines:
        if MARKER in line and line.strip().startswith("# >>>"):
            inside = True
            continue
        if MARKER in line and line.strip().startswith("# <<<"):
            inside = False
            continue
        if not inside:
            kept.append(line)
    path.write_text("\n".join(kept).strip() + "\n", encoding="utf-8")


@pytest.mark.unit
class TestDeclarationSchema:
    """The key is additive, lenient about absence, and strict about breakage."""

    def test_absent_declaration_reads_as_managed(self, tmp_path: Path) -> None:
        assert read_blocks_declaration(tmp_path) == BlocksDeclaration()

    def test_an_explicit_decline_round_trips(self, tmp_path: Path) -> None:
        (tmp_path / ".vaultspec").mkdir()

        write_blocks_declaration(tmp_path, BlocksDeclaration(gitignore=False))

        assert read_blocks_declaration(tmp_path) == BlocksDeclaration(
            gitignore=False, gitattributes=True
        )

    def test_the_default_writes_no_key(self, tmp_path: Path) -> None:
        """A workspace that has never declined keeps a byte-identical file."""
        (tmp_path / ".vaultspec").mkdir()
        write_blocks_declaration(tmp_path, BlocksDeclaration())

        raw = (tmp_path / ".vaultspec" / "workspace.json").read_text(encoding="utf-8")

        assert "blocks" not in raw

    def test_writing_blocks_preserves_the_hook_policy(self, tmp_path: Path) -> None:
        """The document is written whole, so neither half may drop the other."""
        (tmp_path / ".vaultspec").mkdir()
        write_hooks_declaration(tmp_path, HooksDeclaration(pre_commit=False))

        write_blocks_declaration(tmp_path, BlocksDeclaration(gitattributes=False))

        assert read_hooks_declaration(tmp_path).pre_commit is False
        assert read_blocks_declaration(tmp_path).gitattributes is False

    def test_writing_hooks_preserves_the_block_policy(self, tmp_path: Path) -> None:
        (tmp_path / ".vaultspec").mkdir()
        write_blocks_declaration(tmp_path, BlocksDeclaration(gitignore=False))

        write_hooks_declaration(tmp_path, HooksDeclaration(pre_commit=False))

        assert read_blocks_declaration(tmp_path).gitignore is False
        assert read_hooks_declaration(tmp_path).pre_commit is False

    def test_a_malformed_blocks_object_raises(self, tmp_path: Path) -> None:
        """Silently ignoring a broken opt-out would rewrite the declined block."""
        (tmp_path / ".vaultspec").mkdir()
        (tmp_path / ".vaultspec" / "workspace.json").write_text(
            '{"schema_version": "2.2", "packages": {}, "blocks": "nope"}',
            encoding="utf-8",
        )

        with pytest.raises(VaultSpecError):
            read_blocks_declaration(tmp_path)

    def test_a_non_boolean_block_value_raises(self, tmp_path: Path) -> None:
        (tmp_path / ".vaultspec").mkdir()
        (tmp_path / ".vaultspec" / "workspace.json").write_text(
            '{"schema_version": "2.2", "packages": {}, '
            '"blocks": {"gitignore": "false"}}',
            encoding="utf-8",
        )

        with pytest.raises(VaultSpecError):
            read_blocks_declaration(tmp_path)


@pytest.mark.unit
class TestResolutionPrecedence:
    """The declaration decides; the per-machine flag is only an echo."""

    def test_undeclared_and_unflagged_is_managed(self, tmp_path: Path) -> None:
        assert block_management_enabled(tmp_path, "gitignore") is True

    def test_a_committed_decline_wins(self, tmp_path: Path) -> None:
        (tmp_path / ".vaultspec").mkdir()
        write_blocks_declaration(tmp_path, BlocksDeclaration(gitignore=False))

        assert block_management_enabled(tmp_path, "gitignore") is False

    def test_the_local_echo_still_declines(self, tmp_path: Path) -> None:
        """A machine that stood down before the declaration existed is honoured."""
        factory = WorkspaceFactory(tmp_path)
        factory.install()
        mdata = read_manifest_data(tmp_path)
        mdata.gitignore_opted_out = True
        write_manifest_data(tmp_path, mdata)

        assert block_management_enabled(tmp_path, "gitignore") is False

    def test_each_block_resolves_independently(self, tmp_path: Path) -> None:
        (tmp_path / ".vaultspec").mkdir()
        write_blocks_declaration(tmp_path, BlocksDeclaration(gitignore=False))

        assert block_management_enabled(tmp_path, "gitignore") is False
        assert block_management_enabled(tmp_path, "gitattributes") is True


@pytest.mark.integration
class TestTheVerbs:
    """Four verbs over one implementation, idempotent, each writing one key."""

    def test_disable_records_a_committed_decline(self, tmp_path: Path) -> None:
        factory = WorkspaceFactory(tmp_path)
        factory.install()

        result = factory.run("spec", "gitignore", "disable")

        assert result.exit_code == 0
        assert read_blocks_declaration(tmp_path).gitignore is False

    def test_disable_is_idempotent(self, tmp_path: Path) -> None:
        factory = WorkspaceFactory(tmp_path)
        factory.install()
        factory.run("spec", "gitignore", "disable")

        result = factory.run("spec", "gitignore", "disable")

        assert result.exit_code == 0
        assert "unchanged" in result.output

    def test_enable_on_an_undeclared_workspace_is_a_no_op(self, tmp_path: Path) -> None:
        factory = WorkspaceFactory(tmp_path)
        factory.install()

        result = factory.run("spec", "gitignore", "enable")

        assert result.exit_code == 0
        assert "unchanged" in result.output

    def test_enable_clears_a_decline(self, tmp_path: Path) -> None:
        factory = WorkspaceFactory(tmp_path)
        factory.install()
        factory.run("spec", "gitignore", "disable")

        factory.run("spec", "gitignore", "enable")

        assert read_blocks_declaration(tmp_path).gitignore is True

    def test_each_verb_writes_only_its_own_key(self, tmp_path: Path) -> None:
        factory = WorkspaceFactory(tmp_path)
        factory.install()

        factory.run("spec", "gitattributes", "disable")

        declaration = read_blocks_declaration(tmp_path)
        assert declaration.gitattributes is False
        assert declaration.gitignore is True


@pytest.mark.integration
class TestTheDecisionSurvivesAClone:
    """The sequence in the research that fails before this work.

    One contributor declines; a second clones and installs; the second must not
    silently restore what the first declined.
    """

    def _declining_origin(self, root: Path) -> WorkspaceFactory:
        _run_git(root, "init", "-q", "-b", "main")
        factory = WorkspaceFactory(root)
        factory.install(provider="claude")
        factory.run("spec", "gitignore", "disable")
        _strip_block(root / ".gitignore")
        _run_git(root, "add", "-A")
        _run_git(root, "commit", "-q", "-m", "decline the managed block")
        return factory

    def test_a_clone_does_not_restore_the_declined_block(self, tmp_path: Path) -> None:
        origin = tmp_path / "origin"
        origin.mkdir()
        self._declining_origin(origin)

        clone = tmp_path / "clone"
        _run_git(tmp_path, "clone", "-q", str(origin), str(clone))
        WorkspaceFactory.wrap(clone).install(provider="claude", force=True)

        assert MARKER not in (clone / ".gitignore").read_text(encoding="utf-8")

    def test_a_clone_still_gets_the_block_it_did_not_decline(
        self, tmp_path: Path
    ) -> None:
        origin = tmp_path / "origin"
        origin.mkdir()
        self._declining_origin(origin)

        clone = tmp_path / "clone"
        _run_git(tmp_path, "clone", "-q", str(origin), str(clone))
        WorkspaceFactory.wrap(clone).install(provider="claude", force=True)

        assert MARKER in (clone / ".gitattributes").read_text(encoding="utf-8")

    def test_force_does_not_reverse_a_committed_decline(self, tmp_path: Path) -> None:
        """`--force` clears the per-machine echo, never the team's decision."""
        factory = WorkspaceFactory(tmp_path)
        factory.install()
        factory.run("spec", "gitignore", "disable")
        _strip_block(tmp_path / ".gitignore")

        factory.install(upgrade=True, force=True)

        assert read_blocks_declaration(tmp_path).gitignore is False
        assert MARKER not in (tmp_path / ".gitignore").read_text(encoding="utf-8")

    def test_the_verb_is_what_reverses_it(self, tmp_path: Path) -> None:
        factory = WorkspaceFactory(tmp_path)
        factory.install()
        factory.run("spec", "gitignore", "disable")
        _strip_block(tmp_path / ".gitignore")

        factory.run("spec", "gitignore", "enable")
        factory.install(upgrade=True)

        assert MARKER in (tmp_path / ".gitignore").read_text(encoding="utf-8")


@pytest.mark.integration
class TestSyncNeverWritesTheDeclaration:
    """Inference stands the machine down; it does not speak for the project."""

    def test_deleting_the_block_leaves_the_declaration_alone(
        self, tmp_path: Path
    ) -> None:
        factory = WorkspaceFactory(tmp_path)
        factory.install()
        _strip_block(tmp_path / ".gitignore")

        factory.sync()

        assert read_blocks_declaration(tmp_path).gitignore is True
        assert read_manifest_data(tmp_path).gitignore_opted_out is True


@pytest.mark.integration
class TestGitattributesParity:
    """The twin gains the upgrade reconciliation and the decode handling."""

    def test_upgrade_restores_a_deleted_gitattributes_block(
        self, tmp_path: Path
    ) -> None:
        factory = WorkspaceFactory(tmp_path)
        factory.install()
        (tmp_path / ".gitattributes").unlink()

        factory.install(upgrade=True)

        assert MARKER in (tmp_path / ".gitattributes").read_text(encoding="utf-8")

    def test_a_committed_decline_stops_that_reconciliation(
        self, tmp_path: Path
    ) -> None:
        factory = WorkspaceFactory(tmp_path)
        factory.install()
        factory.run("spec", "gitattributes", "disable")
        (tmp_path / ".gitattributes").unlink()

        factory.install(upgrade=True)

        assert not (tmp_path / ".gitattributes").exists()

    def test_an_undecodable_gitattributes_raises_a_typed_error(
        self, tmp_path: Path
    ) -> None:
        """It used to surface as a raw traceback from `install --force`."""
        from vaultspec_core.core.enums import ManagedState
        from vaultspec_core.core.gitattributes import ensure_gitattributes_block

        (tmp_path / ".gitattributes").write_bytes(b"\xff\xfe\x00garbage\n")

        with pytest.raises(VaultSpecError):
            ensure_gitattributes_block(tmp_path, state=ManagedState.PRESENT)


@pytest.mark.unit
class TestUnknownKeysSurviveAWrite:
    """A key this build does not know must not be dropped by its writes.

    The declaration is emitted whole, so every write rebuilds the document from
    the parts the writer knows about. Before this, a key added by a newer
    release or by a companion package was silently discarded on the next mode
    or hook write - which for an opt-out means a committed decision quietly
    reverting to its default.
    """

    def test_a_future_key_round_trips(self, tmp_path: Path) -> None:
        (tmp_path / ".vaultspec").mkdir()
        (tmp_path / ".vaultspec" / "workspace.json").write_text(
            '{"schema_version": "2.9", "packages": {}, "future_key": {"x": 1}}',
            encoding="utf-8",
        )

        write_blocks_declaration(tmp_path, BlocksDeclaration(gitignore=False))

        raw = (tmp_path / ".vaultspec" / "workspace.json").read_text(encoding="utf-8")
        assert '"future_key"' in raw
        assert read_blocks_declaration(tmp_path).gitignore is False

    def test_a_hook_write_preserves_the_block_key_verbatim(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / ".vaultspec").mkdir()
        write_blocks_declaration(tmp_path, BlocksDeclaration(gitignore=False))

        write_hooks_declaration(tmp_path, HooksDeclaration(pre_commit=False))

        assert read_blocks_declaration(tmp_path).gitignore is False


@pytest.mark.integration
class TestTheDoctorRowNamesTheWayOut:
    """A row that reports a condition and no remedy is half a diagnosis."""

    def test_the_unmanaged_row_names_both_gestures(self, tmp_path: Path) -> None:
        factory = WorkspaceFactory(tmp_path)
        factory.install()
        _strip_block(tmp_path / ".gitignore")

        result = factory.run("spec", "doctor")

        assert "unmanaged" in result.output
        assert "spec gitignore disable" in result.output
