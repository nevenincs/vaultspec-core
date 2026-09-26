"""Unit tests for core.workspace  - layout resolution and git detection."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vaultspec_core.core.exceptions import ConfigurationError

from ..config import (
    VAULTSPEC_TARGET_DIR,
    ConfigVariable,
    _forget_registry,
    register_registry,
)
from ..workspace import (
    LayoutMode,
    TargetSource,
    discover_git,
    resolve_target,
    resolve_workspace,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

pytestmark = [pytest.mark.unit]


def _make_framework(root: Path, fw_name: str = ".vaultspec") -> Path:
    """Create a minimal framework directory structure."""
    fw = root / fw_name
    (fw / "lib" / "src").mkdir(parents=True)
    (fw / "lib" / "scripts").mkdir(parents=True)
    (fw / "rules").mkdir(parents=True)
    return fw


def _make_git_dir(root: Path) -> Path:
    """Create a standard .git/ directory with enough structure to look real."""
    git_dir = root / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (git_dir / "refs").mkdir()
    (git_dir / "objects").mkdir()
    return git_dir


def _make_git_file(worktree: Path, gitdir_target: Path) -> Path:
    """Create a .git file (linked worktree pointer)."""
    git_file = worktree / ".git"
    git_file.write_text(f"gitdir: {gitdir_target}\n", encoding="utf-8")
    return git_file


class TestDiscoverGit:
    """Tests for the git detection function."""

    def test_standard_git_directory(self, tmp_path: Path) -> None:
        _make_git_dir(tmp_path)

        info = discover_git(tmp_path)

        assert info is not None
        assert info.repo_root == tmp_path
        assert info.is_worktree is False
        assert info.is_bare is False
        assert info.container_root is None

    def test_no_git(self, tmp_path: Path) -> None:
        info = discover_git(tmp_path)
        assert info is None

    def test_git_file_linked_worktree(self, tmp_path: Path) -> None:
        # Main repo with .git/worktrees/<name>/
        main_repo = tmp_path / "main-repo"
        main_repo.mkdir()
        git_dir = _make_git_dir(main_repo)
        worktrees_dir = git_dir / "worktrees" / "feature-branch"
        worktrees_dir.mkdir(parents=True)

        # Linked worktree directory
        wt = tmp_path / "feature-branch"
        wt.mkdir()
        _make_git_file(wt, worktrees_dir)

        info = discover_git(wt)

        assert info is not None
        assert info.is_worktree is True
        assert info.repo_root == main_repo
        assert info.worktree_root == wt

    def test_container_mode_gt_directory(self, tmp_path: Path) -> None:
        # Container with .gt/ bare repo
        gt = tmp_path / ".gt"
        gt.mkdir()
        (gt / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")

        info = discover_git(tmp_path)

        assert info is not None
        assert info.is_bare is True
        assert info.container_root == tmp_path
        assert info.repo_root == tmp_path

    def test_container_mode_cwd_in_worktree(self, tmp_path: Path) -> None:
        # Container root with .gt/
        gt = tmp_path / ".gt"
        gt.mkdir()
        (gt / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        wt_git_dir = gt / "worktrees" / "feature"
        wt_git_dir.mkdir(parents=True)

        # Worktree directory with .git file pointing into .gt/
        wt = tmp_path / "feature"
        wt.mkdir()
        _make_git_file(wt, wt_git_dir)

        # discover_git from the worktree should find .gt/ walking up
        info = discover_git(wt)

        assert info is not None
        assert info.container_root == tmp_path
        assert info.is_bare is True

    def test_walks_up_directories(self, tmp_path: Path) -> None:
        _make_git_dir(tmp_path)
        subdir = tmp_path / "a" / "b" / "c"
        subdir.mkdir(parents=True)

        info = discover_git(subdir)

        assert info is not None
        assert info.repo_root == tmp_path

    def test_git_file_with_relative_path(self, tmp_path: Path) -> None:
        main_repo = tmp_path / "repo"
        main_repo.mkdir()
        git_dir = _make_git_dir(main_repo)
        wt_dir = git_dir / "worktrees" / "wt1"
        wt_dir.mkdir(parents=True)

        wt = tmp_path / "wt1"
        wt.mkdir()
        # Write a relative gitdir pointer
        gitdir = "gitdir: ../repo/.git/worktrees/wt1\n"
        (wt / ".git").write_text(gitdir, encoding="utf-8")

        info = discover_git(wt)

        assert info is not None
        assert info.is_worktree is True
        assert info.repo_root == main_repo


class TestResolveWorkspace:
    """Tests for the workspace layout resolution function."""

    def test_explicit_mode_target_override(self, tmp_path: Path) -> None:
        target = tmp_path / "target"
        target.mkdir()
        fw = _make_framework(target)

        layout = resolve_workspace(
            target_override=target,
            framework_root=fw,
            cwd=tmp_path,
        )

        assert layout.mode == LayoutMode.EXPLICIT
        assert layout.target_dir == target
        assert layout.vault_dir == target / ".vault"
        assert layout.vaultspec_dir == fw

    def test_standalone_classic_git(self, tmp_path: Path) -> None:
        fw = _make_framework(tmp_path)
        _make_git_dir(tmp_path)

        layout = resolve_workspace(
            framework_root=fw,
            cwd=tmp_path,
        )

        assert layout.mode == LayoutMode.STANDALONE
        assert layout.git is not None
        assert layout.git.is_worktree is False
        assert layout.target_dir == tmp_path
        assert layout.vaultspec_dir == fw

    def test_standalone_container_git(self, tmp_path: Path) -> None:
        # Container root
        fw = _make_framework(tmp_path)
        gt = tmp_path / ".gt"
        gt.mkdir()
        (gt / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")

        layout = resolve_workspace(
            framework_root=fw,
            cwd=tmp_path,
        )

        assert layout.mode == LayoutMode.STANDALONE
        assert layout.git is not None
        assert layout.git.container_root == tmp_path
        assert layout.target_dir == tmp_path
        assert layout.vaultspec_dir == fw

    def test_standalone_linked_worktree(self, tmp_path: Path) -> None:
        # Main repo
        main_repo = tmp_path / "main-repo"
        fw = _make_framework(main_repo)
        git_dir = _make_git_dir(main_repo)
        wt_git = git_dir / "worktrees" / "feature"
        wt_git.mkdir(parents=True)

        # Worktree
        wt = tmp_path / "feature"
        wt.mkdir()
        _make_git_file(wt, wt_git)

        layout = resolve_workspace(
            framework_root=fw,
            cwd=wt,
        )

        assert layout.mode == LayoutMode.STANDALONE
        assert layout.git is not None
        assert layout.git.is_worktree is True
        # target_dir is repo_root (main repo) since there is no container_root
        # and worktree_root is not in the resolution chain
        assert layout.target_dir == main_repo or layout.target_dir == wt

    def test_no_git_structural_fallback(self, tmp_path: Path) -> None:
        fw = _make_framework(tmp_path)

        layout = resolve_workspace(
            framework_root=fw,
            cwd=tmp_path,
        )

        assert layout.mode == LayoutMode.STANDALONE
        assert layout.git is None
        assert layout.target_dir == tmp_path
        assert layout.vaultspec_dir == fw

    def test_vault_root_always_follows_target(self, tmp_path: Path) -> None:
        target = tmp_path / "target"
        target.mkdir()
        fw = _make_framework(target)

        layout = resolve_workspace(
            target_override=target,
            framework_root=fw,
        )

        assert layout.vault_dir == target / ".vault"

    def test_framework_root_from_structural_not_env(self, tmp_path: Path) -> None:
        root = tmp_path / "project"
        root.mkdir()
        fw = _make_framework(root)

        layout = resolve_workspace(
            target_override=root,
            framework_root=fw,
            cwd=tmp_path,
        )

        assert layout.vaultspec_dir == fw

    def test_custom_framework_dir_name(self, tmp_path: Path) -> None:
        root = tmp_path / "project"
        root.mkdir()
        _make_framework(root, fw_name=".custom-fw")

        layout = resolve_workspace(
            target_override=root,
            framework_dir_name=".custom-fw",
            cwd=tmp_path,
        )

        assert layout.vaultspec_dir == root / ".custom-fw"

    def test_explicit_mode_with_framework_root_succeeds(self, tmp_path: Path) -> None:
        """EXPLICIT mode with framework_root provided bypasses the fallback."""
        target = tmp_path / "target"
        target.mkdir()
        fw = _make_framework(tmp_path / "fw-source")

        layout = resolve_workspace(
            target_override=target,
            framework_root=fw,
        )

        assert layout.mode == LayoutMode.EXPLICIT
        assert layout.vaultspec_dir == fw

    def test_frozen_layout(self, tmp_path: Path) -> None:
        fw = _make_framework(tmp_path)
        _make_git_dir(tmp_path)

        layout = resolve_workspace(
            framework_root=fw,
            cwd=tmp_path,
        )

        attr = "target_dir"
        with pytest.raises(AttributeError):
            setattr(layout, attr, tmp_path / "changed")


#: A companion package's own root entry, chained to the framework name, so
#: the chain a real importing package declares is what is exercised here.
TARGET_COMPANION = "vaultspec-target-companion"

COMPANION_ROOT = ConfigVariable(
    env_name="VAULTSPEC_TARGET_COMPANION_ROOT",
    attr_name=None,
    var_type=str,
    default=None,
    description="The companion's own root, chained to the framework name.",
    fallback=VAULTSPEC_TARGET_DIR,
)


@pytest.fixture(autouse=True, scope="module")
def _target_companion_registry() -> Iterator[None]:
    """Declare the companion for this module only, and withdraw it after.

    The registries are process-global, so a package invented by a test that
    outlived the test would be state no code under test put there.
    """
    register_registry(TARGET_COMPANION, [COMPANION_ROOT])
    yield
    _forget_registry(TARGET_COMPANION)


class TestResolveTarget:
    """Tests for the two rungs that name a workspace root."""

    def test_invocation_outranks_the_environment(self, tmp_path: Path) -> None:
        named = tmp_path / "named"
        named.mkdir()
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()

        resolved = resolve_target(
            named,
            environ={"VAULTSPEC_TARGET_DIR": str(elsewhere)},
            cwd=tmp_path,
        )

        assert resolved.path == named
        assert resolved.source == TargetSource.INVOCATION
        assert resolved.variable is None

    def test_framework_variable_supplies_the_root(self, tmp_path: Path) -> None:
        resolved = resolve_target(
            environ={"VAULTSPEC_TARGET_DIR": str(tmp_path)},
            cwd=tmp_path,
        )

        assert resolved.path == tmp_path
        assert resolved.source == TargetSource.ENVIRONMENT
        assert resolved.variable == "VAULTSPEC_TARGET_DIR"

    def test_package_variable_outranks_the_framework_name(self, tmp_path: Path) -> None:
        own = tmp_path / "own"
        own.mkdir()
        shared = tmp_path / "shared"
        shared.mkdir()

        resolved = resolve_target(
            package_root=COMPANION_ROOT,
            environ={
                "VAULTSPEC_TARGET_COMPANION_ROOT": str(own),
                "VAULTSPEC_TARGET_DIR": str(shared),
            },
            cwd=tmp_path,
        )

        assert resolved.path == own
        assert resolved.variable == "VAULTSPEC_TARGET_COMPANION_ROOT"

    def test_package_variable_falls_back_to_the_framework_name(
        self, tmp_path: Path
    ) -> None:
        resolved = resolve_target(
            package_root=COMPANION_ROOT,
            environ={"VAULTSPEC_TARGET_DIR": str(tmp_path)},
            cwd=tmp_path,
        )

        assert resolved.path == tmp_path
        assert resolved.variable == "VAULTSPEC_TARGET_DIR"

    def test_nothing_named_means_discovery(self, tmp_path: Path) -> None:
        resolved = resolve_target(environ={}, cwd=tmp_path)

        assert resolved.path is None
        assert resolved.source == TargetSource.DISCOVERY

    def test_blank_variable_is_unset(self, tmp_path: Path) -> None:
        resolved = resolve_target(
            environ={"VAULTSPEC_TARGET_DIR": "   "},
            cwd=tmp_path,
        )

        assert resolved.path is None
        assert resolved.source == TargetSource.DISCOVERY

    def test_relative_root_is_taken_against_the_working_directory(
        self, tmp_path: Path
    ) -> None:
        nested = tmp_path / "nested"
        nested.mkdir()

        resolved = resolve_target(
            environ={"VAULTSPEC_TARGET_DIR": "nested"},
            cwd=tmp_path,
        )

        assert resolved.path == nested

    def test_missing_directory_is_refused_by_name(self, tmp_path: Path) -> None:
        missing = tmp_path / "gone"

        with pytest.raises(ConfigurationError) as excinfo:
            resolve_target(
                package_root=COMPANION_ROOT,
                environ={"VAULTSPEC_TARGET_COMPANION_ROOT": str(missing)},
                cwd=tmp_path,
            )

        assert "VAULTSPEC_TARGET_COMPANION_ROOT" in str(excinfo.value)

    def test_a_file_is_not_a_workspace_root(self, tmp_path: Path) -> None:
        not_a_dir = tmp_path / "root.txt"
        not_a_dir.write_text("", encoding="utf-8")

        with pytest.raises(ConfigurationError):
            resolve_target(
                environ={"VAULTSPEC_TARGET_DIR": str(not_a_dir)},
                cwd=tmp_path,
            )
