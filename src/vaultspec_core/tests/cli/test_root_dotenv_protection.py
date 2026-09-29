"""The workspace-root ``.env`` is protected like the private store.

The credential resolver reads a key from ``<workspace>/.env``, so that file
holds secrets. These tests hold every layer to that: the managed ignore block
keeps it and its variants out of Git while the ``.env.example`` template stays
committable, the commit gate refuses it when force-added, install never
auto-untracks it, and doctor warns when the index already tracks it.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.cli.spec_cmd_doctor import doctor_exit_code
from vaultspec_core.config.local_env import (
    is_local_environment_path,
    tracked_root_environment_files,
)
from vaultspec_core.core.diagnosis import HomeDiagnosis, WorkspaceDiagnosis, diagnose
from vaultspec_core.core.diagnosis.signals import FrameworkSignal
from vaultspec_core.core.git_artifacts import (
    check_staged_provider_artifacts,
    untrack_managed_paths,
)
from vaultspec_core.core.gitignore import get_recommended_entries

if TYPE_CHECKING:
    from pathlib import Path


def _git(
    root: Path, *args: str, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=check,
    )


def _repo(project: Path) -> Path:
    _git(project, "init", "-q")
    _git(project, "config", "user.email", "test@vaultspec.local")
    _git(project, "config", "user.name", "vaultspec-test")
    return project


def _ignored(root: Path, path: str) -> bool:
    return _git(root, "check-ignore", "-q", "--", path, check=False).returncode == 0


@pytest.mark.unit
@pytest.mark.parametrize(
    ("path", "credential"),
    [
        (".env", True),
        (".env.local", True),
        (".env.production", True),
        (".env.example", False),
        (".envrc", False),
        ("env", False),
        ("services/api/.env", False),
        (".vaultspec/.env", True),
        ("nested/.vaultspec/.env.abc.tmp", True),
    ],
)
def test_credential_paths_include_the_root_dotenv(path: str, credential: bool) -> None:
    assert is_local_environment_path(path) is credential


@pytest.mark.unit
def test_the_template_negation_follows_the_glob_it_reincludes(tmp_path: Path) -> None:
    """Git applies a negation only to the patterns above it."""
    entries = get_recommended_entries(tmp_path)

    assert {"/.env", "/.env.*", "!/.env.example"} <= set(entries)
    assert entries.index("!/.env.example") > entries.index("/.env.*")
    assert entries[-1].startswith("!")


@pytest.mark.integration
class TestInstalledWorkspace:
    """Against the block a real install writes, in a real repository."""

    def test_the_block_ignores_the_root_dotenv_but_not_its_template(
        self, synthetic_project: Path
    ) -> None:
        root = _repo(synthetic_project)

        assert _ignored(root, ".env")
        assert _ignored(root, ".env.local")
        assert not _ignored(root, ".env.example")

    def test_the_commit_gate_refuses_a_force_added_root_dotenv(
        self, synthetic_project: Path
    ) -> None:
        root = _repo(synthetic_project)
        (root / ".env").write_text("SECRET=fake\n", encoding="utf-8")
        (root / ".env.local").write_text("SECRET=fake\n", encoding="utf-8")
        (root / ".env.example").write_text("SECRET=\n", encoding="utf-8")
        _git(root, "add", "-f", ".env", ".env.local", ".env.example")

        assert sorted(check_staged_provider_artifacts(root)) == [".env", ".env.local"]

    def test_install_leaves_a_tracked_root_dotenv_to_the_operator(
        self, synthetic_project: Path
    ) -> None:
        """A credential in the index needs rotating, not a silent untrack."""
        root = _repo(synthetic_project)
        (root / ".env").write_text("SECRET=fake\n", encoding="utf-8")
        _git(root, "add", "-f", ".env")

        assert untrack_managed_paths(root, get_recommended_entries(root)) == []
        assert ".env" in _git(root, "ls-files").stdout.splitlines()

    def test_diagnosis_names_a_tracked_root_dotenv_until_it_is_untracked(
        self, synthetic_project: Path
    ) -> None:
        root = _repo(synthetic_project)
        (root / ".env").write_text("SECRET=fake\n", encoding="utf-8")
        (root / ".env.example").write_text("SECRET=\n", encoding="utf-8")
        _git(root, "add", "-f", ".env", ".env.example")
        _git(root, "commit", "-q", "-m", "leak")

        assert tracked_root_environment_files(root) == [".env"]
        assert diagnose(root).tracked_credentials == [".env"]

        _git(root, "rm", "-q", "--cached", ".env")

        assert diagnose(root).tracked_credentials == []


@pytest.mark.unit
class TestDoctorWeight:
    @staticmethod
    def _diagnosis(tracked: list[str] | None) -> WorkspaceDiagnosis:
        return WorkspaceDiagnosis(
            framework=FrameworkSignal.PRESENT,
            home=HomeDiagnosis(tracked_credentials=tracked),
        )

    def test_a_tracked_root_dotenv_is_a_warning(self) -> None:
        assert doctor_exit_code(self._diagnosis([])) == 0
        assert doctor_exit_code(self._diagnosis([".env"])) == 1

    def test_an_unreadable_index_is_not_reported_clean(self) -> None:
        assert doctor_exit_code(self._diagnosis(None)) == 1
