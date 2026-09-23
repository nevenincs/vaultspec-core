"""Hosted-search credential resolution over real workspaces on disk."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vaultspec_core.config import CONFIG_REGISTRY
from vaultspec_core.core.enums import DirName, InstallMode
from vaultspec_core.core.install_mode import write_mode_declaration
from vaultspec_core.core.workspace_mode import WORKSPACE_FILENAME
from vaultspec_core.search import CredentialSource, HostedSearchConfig
from vaultspec_core.search._credential import (
    CREDENTIAL_VARIABLE,
    Credential,
    hosted_search_config,
    resolve_credential,
)

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]

ENV_KEY = "ts-env-7a1d93c0b5e2"
DOTENV_KEY = "ts-dotenv-2c8e41f6a9d0"


def _workspace(
    root: Path, *, mode: InstallMode | None = None, dotenv: str | None = None
) -> Path:
    """Build a workspace whose install mode and ``.env`` are as given."""
    root.mkdir(parents=True, exist_ok=True)
    if mode is not None:
        write_mode_declaration(root, mode)
    if dotenv is not None:
        (root / ".env").write_text(dotenv, encoding="utf-8")
    return root


def _own_env(root: Path) -> Path:
    """The interpreter prefix of a project environment inside *root*."""
    return root / ".venv"


def _dotenv_line(value: str) -> str:
    return f"# local credentials\n{CREDENTIAL_VARIABLE}={value}\n"


def test_variable_name_comes_from_the_secret_registry_entry() -> None:
    (entry,) = [var for var in CONFIG_REGISTRY if var.env_name == CREDENTIAL_VARIABLE]

    assert CREDENTIAL_VARIABLE == "VAULTSPEC_CORE_TYPESAFE_API_KEY"
    assert entry.secret is True


class TestPrecedence:
    def test_environment_wins_over_dotenv(self, tmp_path: Path) -> None:
        root = _workspace(
            tmp_path, mode=InstallMode.DEV, dotenv=_dotenv_line(DOTENV_KEY)
        )

        credential = resolve_credential(
            root,
            {CREDENTIAL_VARIABLE: f" {ENV_KEY} "},
            interpreter_prefix=_own_env(root),
        )

        assert credential == Credential(ENV_KEY, CredentialSource.ENVIRONMENT)

    @pytest.mark.parametrize("mode", [InstallMode.DEPENDENCY, InstallMode.DEV])
    def test_dotenv_is_read_in_dependency_and_dev_modes(
        self, tmp_path: Path, mode: InstallMode
    ) -> None:
        root = _workspace(tmp_path, mode=mode, dotenv=_dotenv_line(DOTENV_KEY))

        credential = resolve_credential(root, {}, interpreter_prefix=_own_env(root))

        assert credential == Credential(DOTENV_KEY, CredentialSource.DOTENV)

    def test_blank_environment_value_falls_through_to_dotenv(
        self, tmp_path: Path
    ) -> None:
        root = _workspace(
            tmp_path, mode=InstallMode.DEPENDENCY, dotenv=_dotenv_line(DOTENV_KEY)
        )

        credential = resolve_credential(
            root, {CREDENTIAL_VARIABLE: "   "}, interpreter_prefix=_own_env(root)
        )

        assert credential == Credential(DOTENV_KEY, CredentialSource.DOTENV)

    def test_blank_environment_value_without_dotenv_is_absent(
        self, tmp_path: Path
    ) -> None:
        root = _workspace(tmp_path, mode=InstallMode.DEPENDENCY)

        assert (
            resolve_credential(
                root, {CREDENTIAL_VARIABLE: ""}, interpreter_prefix=_own_env(root)
            )
            is None
        )

    def test_dev_mode_detected_from_pyproject_opens_dotenv(
        self, tmp_path: Path
    ) -> None:
        root = _workspace(tmp_path, dotenv=_dotenv_line(DOTENV_KEY))
        (root / "pyproject.toml").write_text(
            '[project]\nname = "example"\nversion = "0.0.0"\n\n'
            '[dependency-groups]\ndev = ["vaultspec-core>=0.1"]\n',
            encoding="utf-8",
        )

        credential = resolve_credential(root, {}, interpreter_prefix=_own_env(root))

        assert credential == Credential(DOTENV_KEY, CredentialSource.DOTENV)


class TestClosedDotenv:
    def test_tool_mode_ignores_the_dotenv(self, tmp_path: Path) -> None:
        root = _workspace(
            tmp_path, mode=InstallMode.TOOL, dotenv=_dotenv_line(DOTENV_KEY)
        )

        assert resolve_credential(root, {}, interpreter_prefix=_own_env(root)) is None

    def test_undeclared_workspace_ignores_the_dotenv(self, tmp_path: Path) -> None:
        root = _workspace(tmp_path, dotenv=_dotenv_line(DOTENV_KEY))

        assert resolve_credential(root, {}, interpreter_prefix=_own_env(root)) is None

    def test_corrupt_declaration_ignores_the_dotenv(self, tmp_path: Path) -> None:
        root = _workspace(
            tmp_path, mode=InstallMode.DEV, dotenv=_dotenv_line(DOTENV_KEY)
        )
        declaration = root / DirName.VAULTSPEC.value / WORKSPACE_FILENAME
        declaration.write_text("{not valid json", encoding="utf-8")

        assert resolve_credential(root, {}, interpreter_prefix=_own_env(root)) is None

    def test_a_declared_mode_does_not_open_the_dotenv_to_a_foreign_interpreter(
        self, tmp_path: Path
    ) -> None:
        # A cloned repository declares dev mode and ships a key, but core runs
        # from an interpreter outside it - a uv tool, pipx or a release binary.
        root = _workspace(
            tmp_path / "clone", mode=InstallMode.DEV, dotenv=_dotenv_line(DOTENV_KEY)
        )
        global_tool = tmp_path / "tools" / "vaultspec-core"

        assert resolve_credential(root, {}, interpreter_prefix=global_tool) is None

    def test_the_running_interpreter_is_used_when_no_prefix_is_given(
        self, tmp_path: Path
    ) -> None:
        root = _workspace(
            tmp_path, mode=InstallMode.DEV, dotenv=_dotenv_line(DOTENV_KEY)
        )

        # This test process runs outside tmp_path, so the dotenv stays closed.
        assert resolve_credential(root, {}) is None

    def test_generic_typesafe_variables_never_enrol(self, tmp_path: Path) -> None:
        root = _workspace(
            tmp_path,
            mode=InstallMode.DEV,
            dotenv="TYPESAFE_API_KEY=generic\nVAULTSPEC_RAG_TYPESAFE_API_KEY=rag\n",
        )
        environ = {
            "TYPESAFE_API_KEY": "generic",
            "VAULTSPEC_RAG_TYPESAFE_API_KEY": "rag",
        }

        assert (
            resolve_credential(root, environ, interpreter_prefix=_own_env(root)) is None
        )


class TestDotenvShapes:
    @pytest.mark.parametrize(
        "text",
        [
            f'export {CREDENTIAL_VARIABLE}="{DOTENV_KEY}"\n',
            f"{CREDENTIAL_VARIABLE} = '{DOTENV_KEY}'\n",
            f"{CREDENTIAL_VARIABLE}={DOTENV_KEY}  # personal key\n",
        ],
        ids=["export double-quoted", "spaced single-quoted", "trailing comment"],
    )
    def test_quoted_and_exported_values_resolve(
        self, tmp_path: Path, text: str
    ) -> None:
        root = _workspace(tmp_path, mode=InstallMode.DEPENDENCY, dotenv=text)

        credential = resolve_credential(root, {}, interpreter_prefix=_own_env(root))

        assert credential == Credential(DOTENV_KEY, CredentialSource.DOTENV)

    def test_blank_dotenv_value_is_absent(self, tmp_path: Path) -> None:
        root = _workspace(
            tmp_path, mode=InstallMode.DEPENDENCY, dotenv=f'{CREDENTIAL_VARIABLE}=""\n'
        )

        assert resolve_credential(root, {}, interpreter_prefix=_own_env(root)) is None


class TestReporting:
    def test_repr_never_shows_the_key(self) -> None:
        credential = Credential(ENV_KEY, CredentialSource.ENVIRONMENT)

        assert ENV_KEY not in repr(credential)
        assert "environment" in repr(credential)

    def test_config_reports_source_without_the_key(self, tmp_path: Path) -> None:
        root = _workspace(
            tmp_path, mode=InstallMode.DEV, dotenv=_dotenv_line(DOTENV_KEY)
        )

        from_dotenv = hosted_search_config(root, {}, interpreter_prefix=_own_env(root))
        from_environment = hosted_search_config(
            root, {CREDENTIAL_VARIABLE: ENV_KEY}, interpreter_prefix=_own_env(root)
        )
        unconfigured = hosted_search_config(_workspace(tmp_path / "bare"), {})

        assert from_dotenv == HostedSearchConfig(True, CredentialSource.DOTENV)
        assert from_environment == HostedSearchConfig(
            True, CredentialSource.ENVIRONMENT
        )
        assert unconfigured == HostedSearchConfig(False)
        assert DOTENV_KEY not in repr(from_dotenv)
        assert ENV_KEY not in repr(from_environment)
