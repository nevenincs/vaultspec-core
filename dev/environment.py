"""The development harness's environment, declared once and read in one place.

Every environment variable a module under ``dev/`` reads or sets is a
:class:`HarnessVariable` in :data:`HARNESS_REGISTRY`, and this is the only
module under ``dev/`` that touches :data:`os.environ`. It is the harness's
counterpart of ``vaultspec_core.config.CONFIG_REGISTRY``, kept separate for two
reasons: ``dev.init`` runs before the virtual environment exists, so nothing
here may import the product, and nothing the product ships may depend on the
harness. This module is therefore standard-library only and imports nothing
from the rest of ``dev``.

Ownership is read from the name rather than declared: a ``VAULTSPEC_*`` name
is a harness switch this repository owns, and any other name is a convention
another tool or CI owns and the harness honours. The harness has no internal
markers, so the product's three-way scope has no counterpart here.

A variable the product honours as well (``NO_COLOR``, ``CODEX_HOME``) has its
description in the product registry, not here; its entry says so with
``description=None``, and the repository guard holds the two registries to
that split.

Variables the harness only hands to a child tool as that tool's own
configuration - ``PYAPP_*`` for the release builder, ``FORCE_COLOR`` for a
captured tool - are the child's protocol rather than harness settings. They
travel as the overlay :func:`child_environment` applies, never through a read.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

__all__ = [
    "CODEX_HOME",
    "GITHUB_ACTIONS",
    "HARNESS_REGISTRY",
    "NO_COLOR",
    "PYTHONIOENCODING",
    "RUNNER_TOOL_CACHE",
    "VAULTSPEC_ALLOW_EMPTY_SELECTION",
    "VAULTSPEC_CI_REPORTS",
    "VAULTSPEC_FIX_STRICT",
    "VAULTSPEC_INIT_FORCE",
    "VAULTSPEC_INIT_JSON",
    "VAULTSPEC_VERBOSE",
    "HarnessVariable",
    "child_environment",
    "set_default",
    "value",
]


@dataclass(frozen=True, eq=False)
class HarnessVariable:
    """One environment variable the harness reads or sets.

    Attributes:
        name: The variable's name.
        description: What it does, or ``None`` when the product registry
            declares the same variable and documents it there.
    """

    name: str
    description: str | None


VAULTSPEC_CI_REPORTS: Final = HarnessVariable(
    "VAULTSPEC_CI_REPORTS",
    "Directory the dependency audit writes its JSON report into. Unset or "
    "blank writes nothing.",
)

VAULTSPEC_FIX_STRICT: Final = HarnessVariable(
    "VAULTSPEC_FIX_STRICT",
    "Set by CI. Makes a fix recipe report drift when it had to change something.",
)

VAULTSPEC_ALLOW_EMPTY_SELECTION: Final = HarnessVariable(
    "VAULTSPEC_ALLOW_EMPTY_SELECTION",
    "Set by a test lane that is legitimately allowed to collect nothing.",
)

VAULTSPEC_INIT_JSON: Final = HarnessVariable(
    "VAULTSPEC_INIT_JSON",
    "1, true, yes or on turns on the NDJSON event stream of just init, so the "
    "recipe stays argument-free.",
)

VAULTSPEC_INIT_FORCE: Final = HarnessVariable(
    "VAULTSPEC_INIT_FORCE",
    "1, true, yes or on makes just init run every step, ignoring its stamp.",
)

VAULTSPEC_VERBOSE: Final = HarnessVariable(
    "VAULTSPEC_VERBOSE",
    "Any non-blank value streams every harness step and echoes its command.",
)

RUNNER_TOOL_CACHE: Final = HarnessVariable(
    "RUNNER_TOOL_CACHE",
    "Set by the GitHub Actions runner. When set, downloaded tools are cached "
    "under it instead of beside the project's .venv.",
)

GITHUB_ACTIONS: Final = HarnessVariable(
    "GITHUB_ACTIONS",
    "Set to true by the GitHub Actions runner. Linters then also emit their "
    "findings as workflow annotations.",
)

PYTHONIOENCODING: Final = HarnessVariable(
    "PYTHONIOENCODING",
    "Python's stream encoding. The harness sets it to utf-8 for itself and "
    "every Python child unless it is already set.",
)

NO_COLOR: Final = HarnessVariable("NO_COLOR", None)

CODEX_HOME: Final = HarnessVariable("CODEX_HOME", None)

#: Every variable the harness reads or sets, each declared once.
HARNESS_REGISTRY: Final = (
    VAULTSPEC_CI_REPORTS,
    VAULTSPEC_FIX_STRICT,
    VAULTSPEC_ALLOW_EMPTY_SELECTION,
    VAULTSPEC_INIT_JSON,
    VAULTSPEC_INIT_FORCE,
    VAULTSPEC_VERBOSE,
    RUNNER_TOOL_CACHE,
    GITHUB_ACTIONS,
    PYTHONIOENCODING,
    NO_COLOR,
    CODEX_HOME,
)

#: Identities of the declared entries; an entry built elsewhere is refused.
_REGISTERED: Final = frozenset(id(var) for var in HARNESS_REGISTRY)


def _registered(var: HarnessVariable) -> str:
    """Return *var*'s name, refusing an entry not in :data:`HARNESS_REGISTRY`."""
    if id(var) not in _REGISTERED:
        raise ValueError(f"{var.name} is not declared in HARNESS_REGISTRY")
    return var.name


def value(var: HarnessVariable, environ: Mapping[str, str] | None = None) -> str | None:
    """Return the raw value of declared variable *var*, read now.

    Args:
        var: A :data:`HARNESS_REGISTRY` entry.
        environ: The environment to read; ``None`` reads the process's own.

    Returns:
        The value as set, which may be blank, or ``None`` when unset.

    Raises:
        ValueError: If *var* is not a registry entry.
    """
    env = os.environ if environ is None else environ
    return env.get(_registered(var))


def set_default(var: HarnessVariable, default: str) -> None:
    """Set declared variable *var* in this process unless it is already set.

    Args:
        var: A :data:`HARNESS_REGISTRY` entry.
        default: The value to set when *var* is unset.

    Raises:
        ValueError: If *var* is not a registry entry.
    """
    os.environ.setdefault(_registered(var), default)


def child_environment(
    overlay: Mapping[str, str] | None = None, *, without: Iterable[str] = ()
) -> dict[str, str]:
    """Build a child process's environment from this one.

    Args:
        overlay: Variables set for the child on top of the inherited ones.
        without: Inherited variables the child must not see, removed before
            *overlay* is applied.

    Returns:
        A fresh mapping; changing it never touches this process.
    """
    env = dict(os.environ)
    for name in without:
        env.pop(name, None)
    env.update(overlay or {})
    return env
