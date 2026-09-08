"""Host-tool discovery: what the workstation must already provide.

``init`` provisions the worktree, not the workstation. The distinction is the
whole of what this module enforces. Dependencies pinned by a lockfile inside
the repository are `init`'s job and it installs them; `uv`, `just`, `node`,
`rustup` and `mise` are the operator's, and `init` reports them precisely and
refuses to guess at a package manager.

That refusal is deliberate. A bootstrap that silently installs system packages
is one a person cannot run on a machine they do not administer, cannot run in a
sandbox, and cannot reason about afterwards. Reporting
:data:`dev.exit_codes.INIT_HOST_TOOL_MISSING` with the tool's own installation
URL is a better outcome than a half-provisioned host.

Stdlib-only, by the constraint stated in :mod:`dev.init`.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

#: Matches the first dotted version in a `--version` banner. Every tool this
#: fleet requires prints one, in among a varying amount of other text.
_VERSION = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")


@dataclass(frozen=True)
class Requirement:
    """A tool the workstation must provide.

    Attributes:
        command: The executable name, as it must appear on ``PATH``.
        purpose: What this repository needs it for, in one line.
        install_url: Where a person gets it.
        minimum: The lowest acceptable version, as a dotted string, or ``None``
            when any version will do.
        version_argv: How to ask it its version, when that differs from
            ``(command, "--version")``.
        advisory: When true, absence is reported and does not fail `init`.
            Used for tools only some workflows need - Docker, a container
            runtime, a browser channel.
    """

    command: str
    purpose: str
    install_url: str
    minimum: str | None = None
    version_argv: tuple[str, ...] | None = None
    advisory: bool = False


@dataclass(frozen=True)
class Finding:
    """The outcome of probing one requirement.

    Attributes:
        command: The executable that was probed.
        ok: Whether the requirement is satisfied.
        found: The version that was found, or ``None`` when the tool is absent.
        message: One line stating the outcome and, when it is not satisfied,
            the remedy.
        advisory: Carried through from the requirement.
    """

    command: str
    ok: bool
    found: str | None
    message: str
    advisory: bool


def _version_of(requirement: Requirement) -> str | None:
    """Return the dotted version a tool reports, or ``None``.

    Args:
        requirement: The tool to interrogate.

    Returns:
        The first dotted version in its banner, or ``None`` when it does not
        run or prints nothing recognizable.
    """
    resolved = shutil.which(requirement.command)
    if resolved is None:
        return None
    declared = list(requirement.version_argv or (requirement.command, "--version"))
    argv = [resolved, *declared[1:]]
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    match = _VERSION.search((completed.stdout or "") + (completed.stderr or ""))
    return match.group(0) if match else None


def _tuple(version: str) -> tuple[int, ...]:
    """Return a comparable tuple for a dotted version string.

    Args:
        version: A dotted version, possibly with fewer than three components.

    Returns:
        A three-element tuple of integers, zero-padded.
    """
    parts = [int(part) for part in version.split(".")[:3] if part.isdigit()]
    return tuple(parts + [0] * (3 - len(parts)))


def _absent(requirement: Requirement) -> str:
    """Return the message for a tool that is not on ``PATH``.

    Args:
        requirement: The tool that is missing.

    Returns:
        The one line a person needs: what it was for, and where to get it.
    """
    where = f"Install it from {requirement.install_url}"
    return f"{requirement.command} is not on PATH. {requirement.purpose} {where}"


def check(requirement: Requirement) -> Finding:
    """Probe one requirement.

    Args:
        requirement: The tool to check for.

    Returns:
        The finding, whose ``message`` is the whole of what a person needs.
    """
    if shutil.which(requirement.command) is None:
        return Finding(
            command=requirement.command,
            ok=False,
            found=None,
            message=_absent(requirement),
            advisory=requirement.advisory,
        )
    found = _version_of(requirement)
    if requirement.minimum is None:
        return Finding(
            command=requirement.command,
            ok=True,
            found=found,
            message=f"{requirement.command} {found or '(version unknown)'}",
            advisory=requirement.advisory,
        )
    if found is None:
        return Finding(
            command=requirement.command,
            ok=False,
            found=None,
            message=(
                f"{requirement.command} is installed but did not report a version; "
                f"this repository requires >= {requirement.minimum}. "
                f"See {requirement.install_url}"
            ),
            advisory=requirement.advisory,
        )
    if _tuple(found) < _tuple(requirement.minimum):
        return Finding(
            command=requirement.command,
            ok=False,
            found=found,
            message=(
                f"{requirement.command} {found} is too old; this repository "
                f"requires >= {requirement.minimum}. See {requirement.install_url}"
            ),
            advisory=requirement.advisory,
        )
    return Finding(
        command=requirement.command,
        ok=True,
        found=found,
        message=f"{requirement.command} {found} (requires >= {requirement.minimum})",
        advisory=requirement.advisory,
    )


def check_all(requirements: Iterable[Requirement]) -> list[Finding]:
    """Probe every requirement.

    Args:
        requirements: The tools to check for.

    Returns:
        One finding per requirement, in declaration order. Every requirement is
        probed even after one fails, because a person fixing their workstation
        wants the whole list, not the first item of it.
    """
    return [check(requirement) for requirement in requirements]
