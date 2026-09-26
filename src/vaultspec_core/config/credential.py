"""Where a credential comes from, and who may supply it.

A credential is a secret :data:`~vaultspec_core.config.CONFIG_REGISTRY` entry.
Only the name its entry declares supplies it: the hosted-search key, for
example, is not enrolled by the generic ``TYPESAFE_API_KEY`` or by
vaultspec-rag's own variable, so a key provisioned for another tool never
sends vault content anywhere by accident.

Precedence is the process environment first, then the workspace-root ``.env``
for an entry marked ``workspace_dotenv``. The ``.env`` is repository content,
so it is consulted only when the package that owns the credential is running
from the workspace's own environment: the running interpreter lives inside
the workspace (its project virtual environment) and the workspace runs that
package as a project dependency (``dependency`` or ``dev`` install mode).
Each package's mode is resolved separately, so a workspace that takes one
vaultspec package as a dependency does not thereby open its ``.env`` to
another. The mode alone is not enough, because the repository writes what it
is resolved from: a globally installed package - a uv tool, a pipx install, a
release binary - pointed at a freshly cloned repository has its interpreter
outside that repository, so it never picks up a credential the repository
supplies. Running a project's own environment is already a decision to trust
that project's code. From the file only the one named variable is read, so
repository content can at most supply a key, never a setting. A workspace
mode that cannot be resolved counts as none: the ``.env`` stays closed rather
than opening on a guess.

The key is held in a :class:`Credential` whose ``repr`` omits it, and it is
never logged. Status surfaces carry :class:`HostedSearchConfig`, the
credential's non-secret view: whether a key is configured, and from where.
"""

from __future__ import annotations

import logging
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

#: Install modes in which the workspace runs the owning package from its own
#: environment, and so owns the workspace ``.env`` a credential may be read
#: from.
_DOTENV_MODES: Final = frozenset({InstallMode.DEPENDENCY, InstallMode.DEV})

#: The workspace-root file consulted in those modes.
_DOTENV_NAME: Final = ".env"


class CredentialSource(StrEnum):
    """Where a credential was found."""

    ENVIRONMENT = "environment"
    DOTENV = "dotenv"


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


def _workspace_owns_dotenv(root: Path, interpreter_prefix: Path, package: str) -> bool:
    """Return whether *package* runs from *root*'s own environment.

    Args:
        root: The workspace root.
        interpreter_prefix: The running interpreter's prefix.
        package: The distribution whose install mode for *root* decides
            whether the workspace runs it as a project dependency.

    Returns:
        ``True`` when the interpreter lives inside the workspace and
        *package*'s resolved install mode there is dependency or dev;
        ``False`` otherwise, including when the mode cannot be resolved.
    """
    if not _runs_inside(root, interpreter_prefix):
        return False
    try:
        mode = resolve_install_mode(root, package=package)
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
    package: str | None = None,
) -> Credential | None:
    """Resolve the credential *var* declares for the workspace at *root*.

    Args:
        var: A secret registered entry, of any package's registry.
        root: The workspace root, whose ``.env`` may be read only when *var*
            is marked ``workspace_dotenv`` and the package that declared it
            runs from the workspace's own environment.
        environ: The process environment to read; ``None`` reads the
            process's own.
        interpreter_prefix: The running interpreter's prefix; ``None`` reads
            :data:`sys.prefix`.
        package: The distribution whose install mode gates the workspace
            ``.env``; ``None`` uses the package that declared *var*, which is
            what a caller outside a test wants.

    Returns:
        The credential and its source, or ``None`` when no source supplies a
        non-blank key.

    Raises:
        ValueError: If *var* is not a secret registered entry.
    """
    if not var.secret:
        raise ValueError(f"{var.env_name} is not a credential")
    key = env_value(var, environ)
    if key:
        return Credential(key=key, source=CredentialSource.ENVIRONMENT)
    if not var.workspace_dotenv:
        return None
    # env_value has already refused an entry no registry declares, so the
    # declaring package is known by the time the gate needs it.
    owner = var.package if package is None else package
    if owner is None:
        raise ValueError(f"{var.env_name} is not declared in a registry")
    prefix = Path(sys.prefix) if interpreter_prefix is None else interpreter_prefix
    if not _workspace_owns_dotenv(root, prefix, owner):
        return None
    value = read_dotenv_value(root / _DOTENV_NAME, var.env_name)
    if value is None:
        return None
    return Credential(key=value.strip(), source=CredentialSource.DOTENV)
