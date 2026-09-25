"""Resolve opt-in credentials without loading files into the process environment.

Process presence wins, including an explicit blank that disables the credential.
Next is the protected, explicitly provisioned project-local store in every install
mode. Last is the legacy root ``.env`` for marked credentials only: dependency or
dev mode and an interpreter inside the workspace are both required to trust it.
Only the registered name enables the feature; generic or sibling-tool keys do not.
Status exposes configuration and source, never values.
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Final

from ..core.enums import InstallMode
from ..core.exceptions import VaultSpecError
from ..core.workspace_mode import resolve_install_mode
from .config import env_value
from .dotenv import read_dotenv_value
from .local_env import read_local_environment

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .config import ConfigVariable

__all__ = [
    "Credential",
    "CredentialSource",
    "HostedSearchConfig",
    "resolve_credential",
]

logger = logging.getLogger(__name__)

#: Install modes in which the workspace runs core from its own environment,
#: and so owns the workspace ``.env`` that core may read a credential from.
_DOTENV_MODES: Final = frozenset({InstallMode.DEPENDENCY, InstallMode.DEV})

#: The workspace-root file consulted in those modes.
_DOTENV_NAME: Final = ".env"


class CredentialSource(StrEnum):
    """Where a credential was found."""

    ENVIRONMENT = "environment"
    DOTENV = "dotenv"
    LOCAL_ENV = "local_env"


@dataclass(frozen=True)
class Credential:
    """A resolved credential and where it was found.

    Attributes:
        key: The key itself. Omitted from ``repr`` so the object can appear in
            a log line or a traceback without carrying it.
        source: Which source supplied the key.
    """

    key: str = field(repr=False)
    source: CredentialSource


@dataclass(frozen=True)
class HostedSearchConfig:
    """Whether hosted search is configured, and from where. Never the key."""

    configured: bool
    source: CredentialSource | None = None


def _runs_inside(root: Path, interpreter_prefix: Path) -> bool:
    """Return whether the running interpreter belongs to the workspace at *root*.

    Args:
        root: The workspace root.
        interpreter_prefix: The running interpreter's prefix (``sys.prefix``),
            which is the virtual environment directory inside a venv.

    Returns:
        ``True`` when the prefix lies inside the workspace.
    """
    try:
        return interpreter_prefix.resolve().is_relative_to(root.resolve())
    except OSError:
        return False


def _workspace_owns_dotenv(root: Path, interpreter_prefix: Path) -> bool:
    """Return whether core runs from *root*'s own environment, opening its ``.env``.

    Args:
        root: The workspace root.
        interpreter_prefix: The running interpreter's prefix.

    Returns:
        ``True`` when the interpreter lives inside the workspace and the
        workspace declares dependency or dev install mode; ``False``
        otherwise, including when the declaration cannot be read.
    """
    if not _runs_inside(root, interpreter_prefix):
        return False
    try:
        mode = resolve_install_mode(root)
    except VaultSpecError:
        logger.debug(
            "workspace install mode unreadable; the workspace .env is not consulted"
        )
        return False
    return mode in _DOTENV_MODES


def resolve_credential(
    var: ConfigVariable,
    root: Path,
    environ: Mapping[str, str] | None = None,
    *,
    interpreter_prefix: Path | None = None,
) -> Credential | None:
    """Resolve the credential *var* declares for the workspace at *root*.

    Args:
        var: A secret :data:`~vaultspec_core.config.CONFIG_REGISTRY` entry.
        root: The workspace root, whose ``.env`` may be read only when *var*
            is marked ``workspace_dotenv`` and core runs from the workspace's
            own environment.
        environ: The process environment to read; ``None`` reads the
            process's own.
        interpreter_prefix: The running interpreter's prefix; ``None`` reads
            :data:`sys.prefix`.

    Returns:
        The credential and its source, or ``None`` when no source supplies a
        non-blank key.

    Raises:
        ValueError: If *var* is not a secret registry entry.
    """
    if not var.secret:
        raise ValueError(f"{var.env_name} is not a credential")
    environment = os.environ if environ is None else environ
    value = env_value(var, environment)
    if value is not None:
        key = value.strip()
        return Credential(key=key, source=CredentialSource.ENVIRONMENT) if key else None
    value = read_local_environment(root).get(var.env_name) if var.persistable else None
    if value is not None:
        key = value.strip()
        return Credential(key=key, source=CredentialSource.LOCAL_ENV) if key else None
    if not var.workspace_dotenv:
        return None
    prefix = Path(sys.prefix) if interpreter_prefix is None else interpreter_prefix
    if not _workspace_owns_dotenv(root, prefix):
        return None
    value = read_dotenv_value(root / _DOTENV_NAME, var.env_name)
    if value is None:
        return None
    return Credential(key=value.strip(), source=CredentialSource.DOTENV)
