"""Credential resolution over real workspaces on disk."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vaultspec_core.config import (
    CONFIG_REGISTRY,
    VAULTSPEC_CORE_TYPESAFE_API_KEY,
    VAULTSPEC_EDITOR,
    ConfigVariable,
    Credential,
    CredentialSource,
    resolve_credential,
)
from vaultspec_core.core.enums import DirName, InstallMode
from vaultspec_core.core.install_mode import write_mode_declaration
from vaultspec_core.core.workspace_mode import WORKSPACE_FILENAME

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]

KEY_VAR = VAULTSPEC_CORE_TYPESAFE_API_KEY
NAME = KEY_VAR.env_name
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
    return f"# local credentials\n{NAME}={value}\n"


class TestTheRegistryOwnsTheCredential:
    def test_the_hosted_search_key_is_the_only_workspace_dotenv_entry(self) -> None:
        eligible = [var for var in CONFIG_REGISTRY if var.workspace_dotenv]

        assert eligible == [KEY_VAR]
        assert NAME == "VAULTSPEC_CORE_TYPESAFE_API_KEY"
        assert KEY_VAR.secret is True

    def test_a_setting_cannot_be_resolved_as_a_credential(self, tmp_path: Path) -> None:
        root = _workspace(tmp_path, mode=InstallMode.DEV)

        with pytest.raises(ValueError, match="is not a credential"):
            resolve_credential(
                VAULTSPEC_EDITOR, root, {VAULTSPEC_EDITOR.env_name: "vi"}
            )

    def test_an_unregistered_secret_is_refused(self, tmp_path: Path) -> None:
        stray = ConfigVariable(
            env_name="VAULTSPEC_UNDECLARED_SECRET",
            attr_name=None,
            var_type=str,
            default=None,
            description="Declared outside the registry.",
            secret=True,
        )

        with pytest.raises(ValueError, match="not declared in CONFIG_REGISTRY"):
            resolve_credential(stray, tmp_path, {stray.env_name: ENV_KEY})

    def test_only_a_secret_may_be_read_from_a_workspace_dotenv(self) -> None:
        with pytest.raises(ValueError, match="only a secret"):
            ConfigVariable(
                env_name="VAULTSPEC_UNDECLARED_SETTING",
                attr_name=None,
                var_type=str,
                default=None,
                description="A setting a repository must not supply.",
                workspace_dotenv=True,
            )


class TestPrecedence:
    def test_environment_wins_over_dotenv(self, tmp_path: Path) -> None:
        root = _workspace(
            tmp_path, mode=InstallMode.DEV, dotenv=_dotenv_line(DOTENV_KEY)
        )

        credential = resolve_credential(
            KEY_VAR, root, {NAME: f" {ENV_KEY} "}, interpreter_prefix=_own_env(root)
        )

        assert credential == Credential(ENV_KEY, CredentialSource.ENVIRONMENT)

    def test_environment_is_read_whatever_the_workspace(self, tmp_path: Path) -> None:
        # Neither gate applies to the process environment: a global tool in an
        # undeclared workspace still takes the key from where the operator set it.
        root = _workspace(tmp_path)

        credential = resolve_credential(
            KEY_VAR, root, {NAME: ENV_KEY}, interpreter_prefix=tmp_path.parent
        )

        assert credential == Credential(ENV_KEY, CredentialSource.ENVIRONMENT)

    @pytest.mark.parametrize("mode", [InstallMode.DEPENDENCY, InstallMode.DEV])
    def test_dotenv_is_read_in_dependency_and_dev_modes(
        self, tmp_path: Path, mode: InstallMode
    ) -> None:
        root = _workspace(tmp_path, mode=mode, dotenv=_dotenv_line(DOTENV_KEY))

        credential = resolve_credential(
            KEY_VAR, root, {}, interpreter_prefix=_own_env(root)
        )

        assert credential == Credential(DOTENV_KEY, CredentialSource.DOTENV)

    def test_blank_environment_value_disables_dotenv(self, tmp_path: Path) -> None:
        root = _workspace(
            tmp_path, mode=InstallMode.DEPENDENCY, dotenv=_dotenv_line(DOTENV_KEY)
        )

        credential = resolve_credential(
            KEY_VAR, root, {NAME: "   "}, interpreter_prefix=_own_env(root)
        )

        assert credential is None

    def test_blank_environment_value_without_dotenv_is_absent(
        self, tmp_path: Path
    ) -> None:
        root = _workspace(tmp_path, mode=InstallMode.DEPENDENCY)

        assert (
            resolve_credential(
                KEY_VAR, root, {NAME: ""}, interpreter_prefix=_own_env(root)
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

        credential = resolve_credential(
            KEY_VAR, root, {}, interpreter_prefix=_own_env(root)
        )

        assert credential == Credential(DOTENV_KEY, CredentialSource.DOTENV)


class TestClosedDotenv:
    def test_tool_mode_ignores_the_dotenv(self, tmp_path: Path) -> None:
        root = _workspace(
            tmp_path, mode=InstallMode.TOOL, dotenv=_dotenv_line(DOTENV_KEY)
        )

        assert (
            resolve_credential(KEY_VAR, root, {}, interpreter_prefix=_own_env(root))
            is None
        )

    def test_undeclared_workspace_ignores_the_dotenv(self, tmp_path: Path) -> None:
        root = _workspace(tmp_path, dotenv=_dotenv_line(DOTENV_KEY))

        assert (
            resolve_credential(KEY_VAR, root, {}, interpreter_prefix=_own_env(root))
            is None
        )

    def test_corrupt_declaration_ignores_the_dotenv(self, tmp_path: Path) -> None:
        root = _workspace(
            tmp_path, mode=InstallMode.DEV, dotenv=_dotenv_line(DOTENV_KEY)
        )
        declaration = root / DirName.VAULTSPEC.value / WORKSPACE_FILENAME
        declaration.write_text("{not valid json", encoding="utf-8")

        assert (
            resolve_credential(KEY_VAR, root, {}, interpreter_prefix=_own_env(root))
            is None
        )

    def test_a_declared_mode_does_not_open_the_dotenv_to_a_foreign_interpreter(
        self, tmp_path: Path
    ) -> None:
        # A cloned repository declares dev mode and ships a key, but core runs
        # from an interpreter outside it - a uv tool, pipx or a release binary.
        root = _workspace(
            tmp_path / "clone", mode=InstallMode.DEV, dotenv=_dotenv_line(DOTENV_KEY)
        )
        global_tool = tmp_path / "tools" / "vaultspec-core"

        assert (
            resolve_credential(KEY_VAR, root, {}, interpreter_prefix=global_tool)
            is None
        )

    def test_the_running_interpreter_is_used_when_no_prefix_is_given(
        self, tmp_path: Path
    ) -> None:
        root = _workspace(
            tmp_path, mode=InstallMode.DEV, dotenv=_dotenv_line(DOTENV_KEY)
        )

        # This test process runs outside tmp_path, so the dotenv stays closed.
        assert resolve_credential(KEY_VAR, root, {}) is None

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
            resolve_credential(
                KEY_VAR, root, environ, interpreter_prefix=_own_env(root)
            )
            is None
        )


class TestDotenvShapes:
    @pytest.mark.parametrize(
        "text",
        [
            f'export {NAME}="{DOTENV_KEY}"\n',
            f"{NAME} = '{DOTENV_KEY}'\n",
            f"{NAME}={DOTENV_KEY}  # personal key\n",
        ],
        ids=["export double-quoted", "spaced single-quoted", "trailing comment"],
    )
    def test_quoted_and_exported_values_resolve(
        self, tmp_path: Path, text: str
    ) -> None:
        root = _workspace(tmp_path, mode=InstallMode.DEPENDENCY, dotenv=text)

        credential = resolve_credential(
            KEY_VAR, root, {}, interpreter_prefix=_own_env(root)
        )

        assert credential == Credential(DOTENV_KEY, CredentialSource.DOTENV)

    def test_blank_dotenv_value_is_absent(self, tmp_path: Path) -> None:
        root = _workspace(tmp_path, mode=InstallMode.DEPENDENCY, dotenv=f'{NAME}=""\n')

        assert (
            resolve_credential(KEY_VAR, root, {}, interpreter_prefix=_own_env(root))
            is None
        )


def test_repr_never_shows_the_key() -> None:
    credential = Credential(ENV_KEY, CredentialSource.ENVIRONMENT)

    assert ENV_KEY not in repr(credential)
    assert "environment" in repr(credential)
