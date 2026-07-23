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
    managed_lock_paths,
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
        assert expected <= set(managed_lock_paths(tmp_path))
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
