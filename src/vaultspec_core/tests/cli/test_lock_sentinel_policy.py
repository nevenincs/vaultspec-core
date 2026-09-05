"""Regression tests for managed-ignore coverage of advisory-lock sentinels.

``advisory_lock`` leaves a sibling ``<path>.lock`` next to every file
vaultspec locks, so the managed ``.gitignore`` block must cover the exact
set of sentinels an install can generate.  Historically the ignore policy
and the untracking ownership gate each hardcoded a root-level list, which
silently missed the provider-native MCP configurations
(``.codex/config.toml``, ``.agents/mcp_config.json``) and left their
sentinels visible in ``git status``.

These tests compare the sentinels a real install actually generates on
disk against the policy derivation, so enrolling a further provider
cannot reintroduce the gap.  Everything runs against the real filesystem
and a real ``git`` subprocess; no mocks, patches, or stubs.
"""

from __future__ import annotations

import os
import subprocess
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.core.gitignore import (
    get_recommended_entries,
    managed_lock_candidates,
    prune_orphaned_lock_sentinels,
)
from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory

if TYPE_CHECKING:
    from pathlib import Path


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


def _generated_lock_files(root: Path) -> list[str]:
    """Return every ``*.lock`` file present under *root*, git metadata aside."""
    return sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*.lock")
        if ".git" not in path.relative_to(root).parts and path.is_file()
    )


def _installed_workspace(root: Path) -> WorkspaceFactory:
    """Install and sync every provider so all lock subjects are realised."""
    factory = WorkspaceFactory(root)
    factory.install(provider="all")
    factory.sync()
    return factory


@pytest.mark.unit
class TestGeneratedSentinelsMatchPolicy:
    """The sentinels an install generates must be the sentinels we declare."""

    def test_provider_sentinels_are_derived_from_mcp_targets(
        self, tmp_path: Path
    ) -> None:
        """Every in-repo MCP target contributes a sentinel to the policy.

        The expectation is derived from ``resolve_mcp_targets`` - the same
        source of truth the lock-taking code consumes - rather than a
        hardcoded path list, so a fifth provider is covered automatically.
        """
        from vaultspec_core.core.mcps import resolve_mcp_targets

        _installed_workspace(tmp_path)

        expected = {
            f"{target.path.relative_to(tmp_path).as_posix()}.lock"
            for target in resolve_mcp_targets(target_dir=tmp_path)
            if target.path.is_relative_to(tmp_path)
        }

        assert expected, "install should enrol at least one in-repo MCP target"
        assert expected <= set(managed_lock_candidates(tmp_path))

    def test_every_generated_sentinel_is_covered_by_the_policy(
        self, tmp_path: Path
    ) -> None:
        """No sentinel written during install escapes the managed ignore block.

        ``.vaultspec/`` sentinels are covered by the ``.vaultspec/*.lock``
        glob; everything else must be enumerated verbatim.
        """
        _installed_workspace(tmp_path)

        entries = set(get_recommended_entries(tmp_path))
        generated = _generated_lock_files(tmp_path)

        assert generated, "install should generate at least one lock sentinel"
        uncovered = [
            lock
            for lock in generated
            if f"/{lock}" not in entries
            and not (lock.startswith(".vaultspec/") and ".vaultspec/*.lock" in entries)
        ]
        assert uncovered == [], (
            f"generated sentinels missing from the managed block: {uncovered!r}"
        )

    def test_policy_covers_the_previously_missed_provider_locks(
        self, tmp_path: Path
    ) -> None:
        """The two sentinels reported in the regression are covered."""
        _installed_workspace(tmp_path)

        entries = set(get_recommended_entries(tmp_path))

        assert "/.codex/config.toml.lock" in entries
        assert "/.agents/mcp_config.json.lock" in entries


@pytest.mark.unit
class TestOrphanedSentinelPruning:
    """Sentinels outliving their subject are retired; foreign locks are not."""

    def test_prek_migration_orphan_is_removed(self, tmp_path: Path) -> None:
        """After a prek migration the pre-commit sentinel is cleaned up."""
        factory = _installed_workspace(tmp_path)
        sentinel = tmp_path / ".pre-commit-config.yaml.lock"
        assert sentinel.is_file()

        (tmp_path / ".pre-commit-config.yaml").unlink()
        (tmp_path / "prek.toml").write_text("", encoding="utf-8")

        factory.sync()

        assert not sentinel.exists()

    def test_prune_reports_what_it_removed(self, tmp_path: Path) -> None:
        _installed_workspace(tmp_path)
        (tmp_path / ".pre-commit-config.yaml").unlink()

        removed = prune_orphaned_lock_sentinels(tmp_path)

        assert removed == [".pre-commit-config.yaml.lock"]
        assert prune_orphaned_lock_sentinels(tmp_path) == []

    def test_non_empty_sentinel_is_left_alone(self, tmp_path: Path) -> None:
        """``advisory_lock`` never writes content, so a non-empty lock is foreign."""
        _installed_workspace(tmp_path)
        (tmp_path / ".pre-commit-config.yaml").unlink()
        foreign = tmp_path / ".pre-commit-config.yaml.lock"
        foreign.write_text("someone else's state", encoding="utf-8")

        removed = prune_orphaned_lock_sentinels(tmp_path)

        assert removed == []
        assert foreign.read_text(encoding="utf-8") == "someone else's state"

    def test_unrelated_lockfiles_are_never_pruned(self, tmp_path: Path) -> None:
        _installed_workspace(tmp_path)
        for name in ("uv.lock", "Cargo.lock", "custom.lock"):
            (tmp_path / name).write_text("", encoding="utf-8")

        prune_orphaned_lock_sentinels(tmp_path)

        for name in ("uv.lock", "Cargo.lock", "custom.lock"):
            assert (tmp_path / name).is_file()


@pytest.mark.integration
class TestCleanRepositoryAfterInstall:
    """A real clone must show zero Core-owned noise after a repeat install."""

    def test_second_install_leaves_no_untracked_core_artefacts(
        self, tmp_path: Path
    ) -> None:
        _run_git(tmp_path, "init", "-q", "-b", "main")
        _run_git(tmp_path, "commit", "--allow-empty", "-q", "-m", "init")

        _installed_workspace(tmp_path)
        _run_git(tmp_path, "add", "-A")
        _run_git(tmp_path, "commit", "-q", "-m", "install vaultspec")

        assert _run_git(tmp_path, "status", "--porcelain").stdout == ""

        second = WorkspaceFactory.wrap(tmp_path)
        second.install(provider="all", upgrade=True)
        second.sync()

        status = _run_git(tmp_path, "status", "--porcelain").stdout
        assert status == "", f"second install left the tree dirty:\n{status}"

    def test_generated_sentinels_are_ignored_by_git(self, tmp_path: Path) -> None:
        """Each sentinel on disk is genuinely ignored, per ``git check-ignore``."""
        _run_git(tmp_path, "init", "-q", "-b", "main")
        _run_git(tmp_path, "commit", "--allow-empty", "-q", "-m", "init")

        _installed_workspace(tmp_path)

        generated = _generated_lock_files(tmp_path)
        assert generated
        not_ignored = [
            lock
            for lock in generated
            if _run_git(tmp_path, "check-ignore", "-q", "--", lock).returncode != 0
        ]
        assert not_ignored == [], (
            f"sentinels not ignored by the managed block: {not_ignored!r}"
        )

    def test_orphaned_sentinel_does_not_survive_a_repeat_install(
        self, tmp_path: Path
    ) -> None:
        """A retired subject's sentinel is gone rather than dirtying the tree."""
        _run_git(tmp_path, "init", "-q", "-b", "main")
        _run_git(tmp_path, "commit", "--allow-empty", "-q", "-m", "init")

        _installed_workspace(tmp_path)
        (tmp_path / ".pre-commit-config.yaml").unlink()
        (tmp_path / "prek.toml").write_text("", encoding="utf-8")
        _run_git(tmp_path, "add", "-A")
        _run_git(tmp_path, "commit", "-q", "-m", "migrate to prek")

        second = WorkspaceFactory.wrap(tmp_path)
        second.install(provider="all", upgrade=True)

        assert not (tmp_path / ".pre-commit-config.yaml.lock").exists()
        status = _run_git(tmp_path, "status", "--porcelain").stdout
        assert ".lock" not in status, f"lock noise after repeat install:\n{status}"


@pytest.mark.unit
class TestPolicyIsIndependentOfDiskState:
    """The entry set is derived from policy, not from a disk snapshot.

    ``get_recommended_entries`` is called BEFORE the writes that create the
    subjects it names, most visibly by ``ensure_gitignore_block``, which locks
    ``.gitignore`` and so produces ``.gitignore.lock`` moments after the block
    listing it has been computed.  A presence filter over the lock subjects
    therefore made block completeness a function of call ordering: the first
    install wrote a block short of what the second one produced.
    """

    def test_entries_do_not_change_when_lock_subjects_are_absent(
        self, tmp_path: Path
    ) -> None:
        """Removing every locked subject leaves the recommended set unchanged."""
        _installed_workspace(tmp_path)

        with_subjects = get_recommended_entries(tmp_path)

        for lock in managed_lock_candidates(tmp_path):
            subject = tmp_path / lock.removesuffix(".lock")
            subject.unlink(missing_ok=True)
            (tmp_path / lock).unlink(missing_ok=True)

        assert get_recommended_entries(tmp_path) == with_subjects

    def test_gitignore_sentinel_is_listed_before_its_subject_exists(
        self, tmp_path: Path
    ) -> None:
        """The block covers its own lock sentinel on a workspace with no ignore file."""
        _installed_workspace(tmp_path)
        (tmp_path / ".gitignore").unlink(missing_ok=True)
        (tmp_path / ".gitignore.lock").unlink(missing_ok=True)

        assert "/.gitignore.lock" in get_recommended_entries(tmp_path)


@pytest.mark.integration
class TestInstallProtectsAWorkspaceWithNothing:
    """A workspace that starts with no ignore file ends up protected.

    This is the end-to-end shape of GH issue 399: the install completed,
    printed the sharing-policy statement claiming runtime by-products stay
    local, exited zero, and left the sentinels it had just written with
    nothing ignoring them.
    """

    def test_install_creates_the_ignore_file_and_writes_the_block(
        self, tmp_path: Path
    ) -> None:
        assert not (tmp_path / ".gitignore").exists()

        _installed_workspace(tmp_path)

        text = (tmp_path / ".gitignore").read_text(encoding="utf-8")
        assert "# >>> vaultspec-managed" in text
        for entry in get_recommended_entries(tmp_path):
            assert entry in text.splitlines()

    def test_first_install_writes_what_a_second_one_would(self, tmp_path: Path) -> None:
        """The block does not converge over two runs; it is right the first time."""
        factory = _installed_workspace(tmp_path)
        first = (tmp_path / ".gitignore").read_bytes()

        factory.install(provider="all", upgrade=True, force=True)

        assert (tmp_path / ".gitignore").read_bytes() == first

    def test_every_generated_sentinel_is_ignored_from_the_first_install(
        self, tmp_path: Path
    ) -> None:
        """Including the ignore file's own sentinel, created by the block write."""
        _run_git(tmp_path, "init", "-q", "-b", "main")

        _installed_workspace(tmp_path)

        assert (tmp_path / ".gitignore.lock").is_file()
        not_ignored = [
            lock
            for lock in _generated_lock_files(tmp_path)
            if _run_git(tmp_path, "check-ignore", "-q", "--", lock).returncode != 0
        ]
        assert not_ignored == [], f"sentinels git still tracks: {not_ignored!r}"


@pytest.mark.integration
class TestUpgradeReconvergence:
    """An upgrade repairs a missing block; it does not override an opt-out."""

    def test_legacy_workspace_converges_without_force(self, tmp_path: Path) -> None:
        """A workspace where management was never established gets a block.

        This is the shape an install by an older version leaves behind: the
        block writer skipped the absent file, so the manifest records neither
        management nor an opt-out and the workspace has been unprotected ever
        since. Repair used to require ``--force``, which nothing told the
        reader to pass.
        """
        from vaultspec_core.core.manifest import (
            read_manifest_data,
            write_manifest_data,
        )

        factory = _installed_workspace(tmp_path)
        (tmp_path / ".gitignore").write_text("# mine\n", encoding="utf-8")
        mdata = read_manifest_data(tmp_path)
        mdata.gitignore_managed = False
        mdata.gitignore_opted_out = False
        write_manifest_data(tmp_path, mdata)

        factory.install(provider="all", upgrade=True)

        text = (tmp_path / ".gitignore").read_text(encoding="utf-8")
        assert "# >>> vaultspec-managed" in text
        assert "# mine" in text

    def test_a_deleted_block_comes_back_on_an_explicit_upgrade(
        self, tmp_path: Path
    ) -> None:
        """Deleting the block stands this machine down; it does not bind an upgrade.

        The gesture is an inference about intent, read while syncing. An
        explicit ``install --upgrade`` is a request, and a request outranks an
        inference made about it - not least because the upgrade runs a sync of
        its own partway through, which would otherwise let the run defeat the
        reconciliation it exists to perform.
        """
        factory = _installed_workspace(tmp_path)
        (tmp_path / ".gitignore").write_text("# mine only\n", encoding="utf-8")
        factory.sync()

        factory.install(provider="all", upgrade=True)

        assert "vaultspec-managed" in (tmp_path / ".gitignore").read_text(
            encoding="utf-8"
        )

    def test_a_declared_decline_does_bind_an_upgrade(self, tmp_path: Path) -> None:
        """What the deleted block cannot say, the declaration says."""
        factory = _installed_workspace(tmp_path)
        factory.run("spec", "gitignore", "disable")
        (tmp_path / ".gitignore").write_text("# mine only\n", encoding="utf-8")

        factory.install(provider="all", upgrade=True)

        assert "vaultspec-managed" not in (tmp_path / ".gitignore").read_text(
            encoding="utf-8"
        )

    def test_force_is_the_re_opt_in_gesture(self, tmp_path: Path) -> None:
        factory = _installed_workspace(tmp_path)
        (tmp_path / ".gitignore").write_text("# mine only\n", encoding="utf-8")
        factory.sync()

        factory.install(provider="all", upgrade=True, force=True)

        assert "vaultspec-managed" in (tmp_path / ".gitignore").read_text(
            encoding="utf-8"
        )


@pytest.mark.integration
class TestOptOutIsRecordedByEitherSync:
    """The managed blocks are repository-level, not per-provider.

    Only `sync all` used to reconcile them, so `sync claude` left a deleted
    block unrecorded - and with the diagnosis weighing an unrecorded absence,
    that is a warning the reader cannot clear without knowing which spelling
    of sync clears it.
    """

    def test_single_provider_sync_records_the_opt_out(self, tmp_path: Path) -> None:
        from vaultspec_core.core.manifest import read_manifest_data

        factory = _installed_workspace(tmp_path)
        (tmp_path / ".gitignore").write_text("# mine only\n", encoding="utf-8")

        factory.sync(provider="claude")

        mdata = read_manifest_data(tmp_path)
        assert mdata.gitignore_opted_out is True
        assert mdata.gitignore_managed is False


@pytest.mark.unit
class TestManagedBlockPresenceIsTriState:
    """ "No block" and "cannot tell" are different answers."""

    def test_absent_file_reports_no_block(self, tmp_path: Path) -> None:
        from vaultspec_core.core.git_artifacts import managed_block_presence

        assert managed_block_presence(tmp_path / ".gitignore") is False

    def test_unreadable_file_reports_unknown(self, tmp_path: Path) -> None:
        from vaultspec_core.core.git_artifacts import managed_block_presence

        (tmp_path / ".gitignore").write_bytes(b"\xff\xfe\x00garbage\n")

        assert managed_block_presence(tmp_path / ".gitignore") is None

    def test_a_directory_reports_unknown(self, tmp_path: Path) -> None:
        from vaultspec_core.core.git_artifacts import managed_block_presence

        (tmp_path / ".gitignore").mkdir()

        assert managed_block_presence(tmp_path / ".gitignore") is None


@pytest.mark.integration
class TestOnlyAReadFileCountsAsTheOptOutGesture:
    """An unreadable file must not become a recorded decision.

    Every state that was not "readable file with no markers" used to collapse
    into the opt-out gesture, because the predicate behind it answered False on
    a read failure. The recorded opt-out then suppressed the degraded diagnosis,
    restoring the silence this work removed - by a route through the writer
    rather than the reader.
    """

    def test_undecodable_file_records_nothing(self, tmp_path: Path) -> None:
        from vaultspec_core.core.manifest import read_manifest_data

        factory = _installed_workspace(tmp_path)
        (tmp_path / ".gitignore").write_bytes(b"\xff\xfe\x00garbage\n")

        factory.sync()

        mdata = read_manifest_data(tmp_path)
        assert mdata.gitignore_opted_out is False
        assert mdata.gitignore_managed is True


@pytest.mark.integration
class TestUninstallRemovesAndDoesNotProvision:
    """Uninstall must not write back a file the workspace deleted.

    `ensure_gitignore_block` creates an absent file now, so the uninstall
    reconciler needed a gate it never had: without one a partial uninstall
    recreated a deleted `.gitignore`, before any sync could read that deletion
    as the opt-out gesture.
    """

    def test_partial_uninstall_does_not_recreate_a_deleted_file(
        self, tmp_path: Path
    ) -> None:
        factory = _installed_workspace(tmp_path)
        (tmp_path / ".gitignore").unlink()

        factory.uninstall(provider="gemini", force=True)

        assert not (tmp_path / ".gitignore").exists()

    def test_partial_uninstall_still_reconciles_a_live_block(
        self, tmp_path: Path
    ) -> None:
        factory = _installed_workspace(tmp_path)

        factory.uninstall(provider="gemini", force=True)

        assert "vaultspec-managed" in (tmp_path / ".gitignore").read_text(
            encoding="utf-8"
        )

    def test_partial_uninstall_respects_a_recorded_opt_out(
        self, tmp_path: Path
    ) -> None:
        factory = _installed_workspace(tmp_path)
        (tmp_path / ".gitignore").write_text("# mine only\n", encoding="utf-8")
        factory.sync()

        factory.uninstall(provider="codex", force=True)

        assert "vaultspec-managed" not in (tmp_path / ".gitignore").read_text(
            encoding="utf-8"
        )
