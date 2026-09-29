"""No ``.env`` file is ever committed.

Dotenv files hold secrets, wherever they sit in the repository. These tests
hold every layer to that: the managed ignore block keeps every ``.env`` and
``.env.*`` file out of Git while ``.env.example`` templates stay committable,
the commit gate refuses one that is force-added, install never auto-untracks
one, and doctor warns when the index already tracks one.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.cli.spec_cmd_doctor import doctor_exit_code
from vaultspec_core.config.local_env import (
    is_local_environment_path,
    tracked_dotenv_files,
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

#: Secret-bearing dotenv files at the root and nested in a subproject.
SECRETS = (".env", ".env.local", "services/api/.env", "services/api/.env.production")

#: Templates, which document variables and hold no values.
TEMPLATES = (".env.example", "services/api/.env.example")


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


def _write(root: Path, *paths: str) -> None:
    for path in paths:
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("SECRET=fake\n", encoding="utf-8")


def _ignored(root: Path, path: str) -> bool:
    return _git(root, "check-ignore", "-q", "--", path, check=False).returncode == 0


@pytest.mark.unit
@pytest.mark.parametrize(
    ("path", "credential"),
    [
        *((path, True) for path in SECRETS),
        *((path, False) for path in TEMPLATES),
        (".envrc", False),
        ("env", False),
        ("docs/environment.md", False),
        (".vaultspec/.env", True),
        ("nested/.vaultspec/.env.abc.tmp", True),
    ],
)
def test_every_dotenv_file_but_a_template_is_a_credential(
    path: str, credential: bool
) -> None:
    assert is_local_environment_path(path) is credential


@pytest.mark.unit
def test_the_template_negation_follows_the_glob_it_reincludes(tmp_path: Path) -> None:
    """Git applies a negation only to the patterns above it."""
    entries = get_recommended_entries(tmp_path)

    assert {".env", ".env.*", "!.env.example"} <= set(entries)
    assert entries.index("!.env.example") > entries.index(".env.*")
    assert entries[-1].startswith("!")


@pytest.mark.integration
class TestInstalledWorkspace:
    """Against the block a real install writes, in a real repository."""

    def test_the_block_ignores_every_dotenv_file_but_templates(
        self, synthetic_project: Path
    ) -> None:
        root = _repo(synthetic_project)

        assert [path for path in SECRETS if not _ignored(root, path)] == []
        assert [path for path in TEMPLATES if _ignored(root, path)] == []

    def test_the_commit_gate_refuses_force_added_dotenv_files(
        self, synthetic_project: Path
    ) -> None:
        root = _repo(synthetic_project)
        _write(root, *SECRETS, *TEMPLATES)
        _git(root, "add", "-f", *SECRETS, *TEMPLATES)

        assert sorted(check_staged_provider_artifacts(root)) == sorted(SECRETS)

    def test_install_leaves_a_tracked_dotenv_file_to_the_operator(
        self, synthetic_project: Path
    ) -> None:
        """A credential in the index needs rotating, not a silent untrack."""
        root = _repo(synthetic_project)
        _write(root, *SECRETS)
        _git(root, "add", "-f", *SECRETS)

        assert untrack_managed_paths(root, get_recommended_entries(root)) == []
        tracked = _git(root, "ls-files").stdout.splitlines()
        assert [path for path in SECRETS if path not in tracked] == []

    def test_diagnosis_names_tracked_dotenv_files_until_they_are_untracked(
        self, synthetic_project: Path
    ) -> None:
        root = _repo(synthetic_project)
        _write(root, *SECRETS, *TEMPLATES)
        _git(root, "add", "-f", *SECRETS, *TEMPLATES)
        _git(root, "commit", "-q", "-m", "leak")

        assert sorted(tracked_dotenv_files(root)) == sorted(SECRETS)
        assert sorted(diagnose(root).tracked_credentials or []) == sorted(SECRETS)

        _git(root, "rm", "-q", "--cached", *SECRETS)

        assert diagnose(root).tracked_credentials == []


@pytest.mark.unit
class TestDoctorWeight:
    @staticmethod
    def _diagnosis(tracked: list[str] | None) -> WorkspaceDiagnosis:
        return WorkspaceDiagnosis(
            framework=FrameworkSignal.PRESENT,
            home=HomeDiagnosis(tracked_credentials=tracked),
        )

    def test_a_tracked_dotenv_file_is_a_warning(self) -> None:
        assert doctor_exit_code(self._diagnosis([])) == 0
        assert doctor_exit_code(self._diagnosis([".env"])) == 1

    def test_an_unreadable_index_is_not_reported_clean(self) -> None:
        assert doctor_exit_code(self._diagnosis(None)) == 1
