"""Tests for install command behavior."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from vaultspec_core.cli import app

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestProviderRegistry:
    """The provider vocabulary derives from one source (the Tool enum)."""

    def test_provider_sets_derive_from_tool_enum(self) -> None:
        from vaultspec_core.core.commands import (
            PROVIDER_TO_TOOLS,
            SYNC_PROVIDERS,
            VALID_PROVIDERS,
        )
        from vaultspec_core.core.enums import Tool

        # Every tool has a single-tool entry; the aggregate selectors are present.
        for tool in Tool:
            assert PROVIDER_TO_TOOLS[tool.value] == [tool]
        assert PROVIDER_TO_TOOLS["all"] == list(Tool)
        assert PROVIDER_TO_TOOLS["core"] == []

        # Derived sets stay consistent with the map - no second hand-listed copy.
        assert set(PROVIDER_TO_TOOLS) == VALID_PROVIDERS
        assert VALID_PROVIDERS - {"core"} == SYNC_PROVIDERS


class TestInstallForce:
    def test_install_without_force_fails_if_exists(
        self, tmp_path: Path, runner: CliRunner
    ) -> None:
        """Without --force, install must fail if .vaultspec/ exists."""
        (tmp_path / ".vaultspec").mkdir()
        result = runner.invoke(app, ["-t", str(tmp_path), "install"])
        assert result.exit_code != 0

    def test_install_force_proceeds_if_exists(
        self, tmp_path: Path, runner: CliRunner
    ) -> None:
        """--force allows reinstall over existing .vaultspec/."""
        (tmp_path / ".vaultspec").mkdir()
        result = runner.invoke(app, ["-t", str(tmp_path), "install", "--force"])
        # Should not error about already installed
        if result.exit_code != 0:
            assert "already installed" not in result.output.lower()

    def test_install_api_refuses_success_when_native_mcp_reconciliation_fails(
        self, tmp_path: Path
    ) -> None:
        """A native-store parse failure is a typed install failure, not success."""
        from vaultspec_core.core.commands import install_run
        from vaultspec_core.core.exceptions import VaultSpecError

        (tmp_path / ".mcp.json").write_text("not valid json", encoding="utf-8")

        with pytest.raises(
            VaultSpecError,
            match="MCP provider-native enrollment failed",
        ):
            install_run(tmp_path, provider="claude", force=True)

    def test_install_cli_exits_nonzero_when_native_mcp_reconciliation_fails(
        self, tmp_path: Path, runner: CliRunner
    ) -> None:
        """The CLI exposes the native-store failure and exits non-zero."""
        (tmp_path / ".mcp.json").write_text("not valid json", encoding="utf-8")

        result = runner.invoke(
            app,
            ["-t", str(tmp_path), "install", "claude", "--force"],
        )

        assert result.exit_code == 1, result.output
        assert "MCP provider-native enrollment failed" in result.output
        assert "Cannot parse" in result.output


class TestInstallJson:
    def test_install_json_stdout_is_parseable(
        self, tmp_path: Path, runner: CliRunner
    ) -> None:
        """JSON mode must not prepend preflight warnings to stdout."""
        result = runner.invoke(app, ["-t", str(tmp_path), "install", "--json"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)["data"]
        assert payload["action"] == "install"
        assert payload["has_mcp"] is True


class TestInstallDryRun:
    def test_dry_run_does_not_use_would_wording(
        self, tmp_path: Path, runner: CliRunner
    ) -> None:
        """--dry-run must NOT use 'Would create:' wording."""
        result = runner.invoke(app, ["-t", str(tmp_path), "install", "--dry-run"])
        assert result.exit_code == 0
        assert "would create" not in result.output.lower()

    def test_dry_run_produces_output(self, tmp_path: Path, runner: CliRunner) -> None:
        """--dry-run must produce tree output."""
        result = runner.invoke(app, ["-t", str(tmp_path), "install", "--dry-run"])
        assert result.exit_code == 0
        assert len(result.output.strip()) > 0

    def test_dry_run_lists_individual_provider_files(
        self, synthetic_project: Path, runner: CliRunner
    ) -> None:
        """On an installed workspace, the preview lists provider files, not just dirs.

        Regression for the sparse install --dry-run output: provider work was
        previewed at directory granularity (a single ``claude (rules)`` line)
        while sync previewed per file. The preview now enumerates the files
        sync would deploy, matching sync's granularity.
        """
        result = runner.invoke(
            app, ["-t", str(synthetic_project), "install", "--force", "--dry-run"]
        )
        assert result.exit_code == 0, result.output
        # An individual builtin rule file appears, not only the directory line.
        assert "vaultspec-cli.builtin.md" in result.output


def _write_pyproject_with_vaultspec(root: Path, *, section: str) -> None:
    """Write a pyproject.toml declaring vaultspec-core in *section*.

    *section* is one of ``"runtime"`` (``[project.dependencies]``) or ``"dev"``
    (the default ``[dependency-groups].dev`` group).
    """
    body = '[project]\nname = "example"\nversion = "0.0.0"\n'
    if section == "runtime":
        body += 'dependencies = ["vaultspec-core"]\n'
    elif section == "dev":
        body += '\n[dependency-groups]\ndev = ["vaultspec-core"]\n'
    (root / "pyproject.toml").write_text(body, encoding="utf-8")


def _advisory_present(output: str) -> bool:
    """Return whether the canonical dependency-leak advisory is in *output*.

    Both strings are whitespace-normalized so the console's line wrapping does
    not break the match. The single canonical constant is the only marker, so
    the advisory wording lives in exactly one place.
    """
    from vaultspec_core.core.workspace_mode import DEPENDENCY_LEAK_ADVISORY

    normalized = " ".join(output.split())
    return " ".join(DEPENDENCY_LEAK_ADVISORY.split()) in normalized


class TestDependencyLeakAdvisory:
    """Moment-of-choice dependency-leak advisory (install-parity ADR D3).

    The advisory fires only when a run newly elects dependency mode - an
    explicit ``--mode dependency`` flag or detection resolving to it - and stays
    silent when the mode is merely read from an existing persisted declaration.
    """

    def test_explicit_dependency_install_warns(
        self, tmp_path: Path, runner: CliRunner
    ) -> None:
        _write_pyproject_with_vaultspec(tmp_path, section="runtime")
        result = runner.invoke(
            app, ["-t", str(tmp_path), "install", "--mode", "dependency"]
        )
        assert result.exit_code == 0, result.output
        assert _advisory_present(result.output)

    def test_detected_dependency_install_warns(
        self, tmp_path: Path, runner: CliRunner
    ) -> None:
        # No --mode flag: detection resolves dependency mode from the runtime
        # dependency listing, which is still a fresh election.
        _write_pyproject_with_vaultspec(tmp_path, section="runtime")
        result = runner.invoke(app, ["-t", str(tmp_path), "install"])
        assert result.exit_code == 0, result.output
        assert _advisory_present(result.output)

    def test_persisted_dependency_reinstall_is_silent(
        self, tmp_path: Path, runner: CliRunner
    ) -> None:
        # First install elects dependency mode and persists it.
        _write_pyproject_with_vaultspec(tmp_path, section="runtime")
        first = runner.invoke(
            app, ["-t", str(tmp_path), "install", "--mode", "dependency"]
        )
        assert first.exit_code == 0, first.output
        assert _advisory_present(first.output)

        # Second install reads the persisted declaration: no fresh choice, so no
        # advisory. This is the core of the review fix.
        second = runner.invoke(app, ["-t", str(tmp_path), "install", "--force"])
        assert second.exit_code == 0, second.output
        assert not _advisory_present(second.output)

    def test_tool_mode_install_is_silent(
        self, tmp_path: Path, runner: CliRunner
    ) -> None:
        result = runner.invoke(app, ["-t", str(tmp_path), "install", "--mode", "tool"])
        assert result.exit_code == 0, result.output
        assert not _advisory_present(result.output)

    def test_dependency_dry_run_persisted_is_silent(
        self, tmp_path: Path, runner: CliRunner
    ) -> None:
        # install --dry-run on a workspace already declaring dependency mode must
        # not print the advisory (the review's explicit verify criterion).
        _write_pyproject_with_vaultspec(tmp_path, section="runtime")
        first = runner.invoke(
            app, ["-t", str(tmp_path), "install", "--mode", "dependency"]
        )
        assert first.exit_code == 0, first.output

        preview = runner.invoke(app, ["-t", str(tmp_path), "install", "--dry-run"])
        assert preview.exit_code == 0, preview.output
        assert not _advisory_present(preview.output)


class TestInstallPathSafety:
    def test_deep_nonexistent_path_rejected(
        self, tmp_path: Path, runner: CliRunner
    ) -> None:
        """Installing to a deeply nested non-existent path must fail."""
        target = tmp_path / "a" / "b" / "c" / "project"
        result = runner.invoke(app, ["-t", str(target), "install"])
        assert result.exit_code != 0
        assert "parent directory does not exist" in result.output.lower()
        # Must NOT have created any directories
        assert not (tmp_path / "a").exists()

    def test_single_level_nonexistent_path_creates_dir(
        self, tmp_path: Path, runner: CliRunner
    ) -> None:
        """Installing to a single-level non-existent path should create it."""
        target = tmp_path / "my-project"
        result = runner.invoke(app, ["-t", str(target), "install"])
        assert result.exit_code == 0
        assert target.exists()
        assert (target / ".vaultspec").exists()

    def test_dry_run_nonexistent_path_no_side_effects(
        self, tmp_path: Path, runner: CliRunner
    ) -> None:
        """Dry-run on a non-existent path must not create the directory."""
        target = tmp_path / "phantom"
        runner.invoke(app, ["-t", str(target), "install", "--dry-run"])
        # The key invariant: dry-run must never create the target directory
        assert not target.exists()


class TestSharingPolicy:
    """install and upgrade state the team-shared gitignore policy."""

    @staticmethod
    def _make_repo(path: Path) -> None:
        """Give *path* the ``.git`` marker ``is_git_repo`` reads.

        A directory is enough: the check is existence-based so it also
        answers for linked worktrees, where ``.git`` is a file.
        """
        path.mkdir(parents=True, exist_ok=True)
        (path / ".git").mkdir()

    def test_install_prints_sharing_policy(
        self, tmp_path: Path, runner: CliRunner
    ) -> None:
        """A fresh install states the spec-layer sharing policy plainly."""
        self._make_repo(tmp_path)
        result = runner.invoke(app, ["-t", str(tmp_path), "install"])
        assert result.exit_code == 0, result.output
        assert "Sharing policy" in result.output

    def test_install_without_a_repository_omits_sharing_policy(
        self, tmp_path: Path, runner: CliRunner
    ) -> None:
        """Outside a repository the statement is a claim about nothing.

        The paragraph says the spec layer "are committed to git so teammates
        inherit your project policy".  In a directory git does not track, no
        commit and no teammate exist, so the install must not say it.
        """
        result = runner.invoke(app, ["-t", str(tmp_path), "install"])
        assert result.exit_code == 0, result.output
        assert "Sharing policy" not in result.output
        assert "committed to git" not in result.output
        # The install itself still happens - only the claim is withheld.
        assert (tmp_path / ".gitignore").exists()
        assert (tmp_path / ".vaultspec").is_dir()

    def test_dry_run_install_omits_sharing_policy(
        self, tmp_path: Path, runner: CliRunner
    ) -> None:
        """A dry-run previews changes; it does not state the policy."""
        result = runner.invoke(app, ["-t", str(tmp_path), "install", "--dry-run"])
        assert result.exit_code == 0
        assert "Sharing policy" not in result.output

    def test_upgrade_off_pre_reversal_block_prints_sharing_policy(
        self, tmp_path: Path, runner: CliRunner
    ) -> None:
        """Upgrading a workspace still on the pre-reversal policy states it."""
        from vaultspec_core.core.gitignore import MARKER_BEGIN, MARKER_END

        self._make_repo(tmp_path)
        runner.invoke(app, ["-t", str(tmp_path), "install"])
        # Plant a pre-reversal managed block (blanket-ignores the spec layer).
        old_block = "\n".join(
            [MARKER_BEGIN, ".vaultspec/", ".mcp.json", ".vault/logs/", MARKER_END]
        )
        (tmp_path / ".gitignore").write_text(
            f"# project\n\n{old_block}\n", encoding="utf-8"
        )

        result = runner.invoke(app, ["-t", str(tmp_path), "install", "--upgrade"])
        assert result.exit_code == 0, result.output
        assert "Sharing policy" in result.output

    def test_upgrade_off_pre_reversal_block_without_a_repository_stays_quiet(
        self, tmp_path: Path, runner: CliRunner
    ) -> None:
        """The upgrade path withholds the same claim on the same grounds."""
        from vaultspec_core.core.gitignore import MARKER_BEGIN, MARKER_END

        runner.invoke(app, ["-t", str(tmp_path), "install"])
        old_block = "\n".join(
            [MARKER_BEGIN, ".vaultspec/", ".mcp.json", ".vault/logs/", MARKER_END]
        )
        (tmp_path / ".gitignore").write_text(
            f"# project\n\n{old_block}\n", encoding="utf-8"
        )

        result = runner.invoke(app, ["-t", str(tmp_path), "install", "--upgrade"])
        assert result.exit_code == 0, result.output
        assert "Sharing policy" not in result.output

    def test_upgrade_of_current_workspace_omits_sharing_policy(
        self, tmp_path: Path, runner: CliRunner
    ) -> None:
        """Re-upgrading an already-team-shared workspace stays quiet."""
        runner.invoke(app, ["-t", str(tmp_path), "install"])

        result = runner.invoke(app, ["-t", str(tmp_path), "install", "--upgrade"])
        assert result.exit_code == 0, result.output
        assert "Sharing policy" not in result.output


class TestUpgradeRestoresVault:
    """An upgrade restores the `.vault/` it manages (issue #415).

    With the directory deleted, `install --upgrade` exited 0 and left it
    absent. Because the recommended ignore entries were derived from the
    directory being present, the managed block was rewritten without its four
    `.vault/` entries - and `doctor` then reported the block complete, because
    the recommended set had shrunk to match it. The upgrade agreed with the
    damage instead of repairing it.
    """

    def test_upgrade_rescaffolds_a_deleted_vault(
        self, tmp_path: Path, runner: CliRunner
    ) -> None:
        import shutil

        runner.invoke(app, ["-t", str(tmp_path), "install"])
        assert (tmp_path / ".vault").is_dir()
        shutil.rmtree(tmp_path / ".vault")

        result = runner.invoke(app, ["-t", str(tmp_path), "install", "--upgrade"])

        assert result.exit_code == 0, result.output
        assert (tmp_path / ".vault").is_dir()

    def test_upgrade_keeps_the_vault_entries_in_the_managed_block(
        self, tmp_path: Path, runner: CliRunner
    ) -> None:
        """The block must not shrink to agree with a missing directory."""
        import shutil

        runner.invoke(app, ["-t", str(tmp_path), "install"])
        gitignore = tmp_path / ".gitignore"
        before = [
            line
            for line in gitignore.read_text(encoding="utf-8").splitlines()
            if line.startswith(".vault/")
        ]
        assert before, "install should have written the .vault/ entries"
        shutil.rmtree(tmp_path / ".vault")

        result = runner.invoke(app, ["-t", str(tmp_path), "install", "--upgrade"])

        assert result.exit_code == 0, result.output
        after = [
            line
            for line in gitignore.read_text(encoding="utf-8").splitlines()
            if line.startswith(".vault/")
        ]
        assert after == before

    def test_upgrade_with_skip_core_leaves_the_vault_alone(
        self, tmp_path: Path, runner: CliRunner
    ) -> None:
        """`--skip core` opts out of core work, and that includes scaffolding."""
        import shutil

        runner.invoke(app, ["-t", str(tmp_path), "install"])
        shutil.rmtree(tmp_path / ".vault")

        result = runner.invoke(
            app, ["-t", str(tmp_path), "install", "--upgrade", "--skip", "core"]
        )

        assert result.exit_code == 0, result.output
        assert not (tmp_path / ".vault").exists()
