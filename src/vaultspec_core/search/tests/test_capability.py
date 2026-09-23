"""Hosted-search configuration as status surfaces report it."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vaultspec_core.config import (
    VAULTSPEC_CORE_TYPESAFE_API_KEY,
    CredentialSource,
    HostedSearchConfig,
)
from vaultspec_core.core.enums import InstallMode
from vaultspec_core.core.install_mode import write_mode_declaration
from vaultspec_core.search import hosted_search_config

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]

NAME = VAULTSPEC_CORE_TYPESAFE_API_KEY.env_name
ENV_KEY = "ts-env-7a1d93c0b5e2"
DOTENV_KEY = "ts-dotenv-2c8e41f6a9d0"


def test_config_reports_source_without_the_key(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    write_mode_declaration(root, InstallMode.DEV)
    (root / ".env").write_text(f"{NAME}={DOTENV_KEY}\n", encoding="utf-8")
    bare = tmp_path / "bare"
    bare.mkdir()

    from_dotenv = hosted_search_config(root, {}, interpreter_prefix=root / ".venv")
    from_environment = hosted_search_config(
        root, {NAME: ENV_KEY}, interpreter_prefix=root / ".venv"
    )
    unconfigured = hosted_search_config(bare, {})

    assert from_dotenv == HostedSearchConfig(True, CredentialSource.DOTENV)
    assert from_environment == HostedSearchConfig(True, CredentialSource.ENVIRONMENT)
    assert unconfigured == HostedSearchConfig(False)
    assert DOTENV_KEY not in repr(from_dotenv)
    assert ENV_KEY not in repr(from_environment)
