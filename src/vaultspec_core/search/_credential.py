"""Where the hosted-search credential comes from, and who may supply it.

Hosted search is enrolled by one variable, declared once in the configuration
registry; no other name enrols it. That excludes the generic
``TYPESAFE_API_KEY`` and vaultspec-rag's own variable, so a key provisioned
for another tool never sends vault content anywhere by accident.

Precedence is the process environment first, then the workspace-root
``.env``. The ``.env`` is repository content, so it is consulted only when core
is running from the workspace's own environment: the running interpreter lives
inside the workspace (its project virtual environment) and the workspace
declares that it runs core as a project dependency (``dependency`` or ``dev``
install mode). The declaration alone is not enough, because the repository
writes it: a globally installed core - a uv tool, a pipx install, a release
binary - pointed at a freshly cloned repository has its interpreter outside
that repository, so it never picks up a credential the repository supplies.
Running a project's own environment is already a decision to trust that
project's code. From the file only this one variable is read; the endpoint and
model are code constants, so repository content can at most supply a key,
never redirect one. A workspace declaration that cannot be read counts as no
declaration: the ``.env`` stays closed rather than opening on a guess.

The key is held in a :class:`Credential` whose ``repr`` omits it, and it is
never logged. Status surfaces use :func:`hosted_search_config`, which reports
only whether a key is configured and from which source.
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Final

from ..config import CONFIG_REGISTRY, read_dotenv_value
from ..core.enums import InstallMode
from ..core.exceptions import VaultSpecError
from ..core.workspace_mode import resolve_install_mode
from ._models import CredentialSource, HostedSearchConfig

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "CREDENTIAL_VARIABLE",
    "Credential",
    "hosted_search_config",
    "resolve_credential",
]

logger = logging.getLogger(__name__)

#: The one variable that enrols hosted search, as its registry entry names it.
CREDENTIAL_VARIABLE: Final = {var.attr_name: var.env_name for var in CONFIG_REGISTRY}[
    "typesafe_api_key"
]

#: Install modes in which the workspace runs core from its own environment,
#: and so owns the workspace ``.env`` that core may read the key from.
_DOTENV_MODES: Final = frozenset({InstallMode.DEPENDENCY, InstallMode.DEV})

#: The workspace-root file consulted in those modes.
_DOTENV_NAME: Final = ".env"


@dataclass(frozen=True)
class Credential:
    """A resolved hosted-search key and where it was found.

    Attributes:
        key: The key itself. Omitted from ``repr`` so the object can appear in
            a log line or a traceback without carrying it.
        source: Which source supplied the key.
    """

    key: str = field(repr=False)
    source: CredentialSource


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
    root: Path,
    environ: Mapping[str, str] | None = None,
    *,
    interpreter_prefix: Path | None = None,
) -> Credential | None:
    """Resolve the hosted-search credential for the workspace at *root*.

    Args:
        root: The workspace root, whose ``.env`` may be read only when core
            runs from the workspace's own environment.
        environ: The process environment to read; ``None`` reads
            :data:`os.environ`.
        interpreter_prefix: The running interpreter's prefix; ``None`` reads
            :data:`sys.prefix`.

    Returns:
        The credential and its source, or ``None`` when no source supplies a
        non-blank key.
    """
    env = os.environ if environ is None else environ
    key = env.get(CREDENTIAL_VARIABLE, "").strip()
    if key:
        return Credential(key=key, source=CredentialSource.ENVIRONMENT)
    prefix = Path(sys.prefix) if interpreter_prefix is None else interpreter_prefix
    if not _workspace_owns_dotenv(root, prefix):
        return None
    value = read_dotenv_value(root / _DOTENV_NAME, CREDENTIAL_VARIABLE)
    if value is None:
        return None
    return Credential(key=value.strip(), source=CredentialSource.DOTENV)


def hosted_search_config(
    root: Path,
    environ: Mapping[str, str] | None = None,
    *,
    interpreter_prefix: Path | None = None,
) -> HostedSearchConfig:
    """Report whether hosted search is configured for *root*, never the key.

    This is local configuration, not liveness: a configured key may still be
    rejected by the provider.

    Args:
        root: The workspace root.
        environ: The process environment to read; ``None`` reads
            :data:`os.environ`.
        interpreter_prefix: The running interpreter's prefix; ``None`` reads
            :data:`sys.prefix`.

    Returns:
        Whether a key is configured, and from which source.
    """
    credential = resolve_credential(
        root, environ, interpreter_prefix=interpreter_prefix
    )
    if credential is None:
        return HostedSearchConfig(configured=False)
    return HostedSearchConfig(configured=True, source=credential.source)
