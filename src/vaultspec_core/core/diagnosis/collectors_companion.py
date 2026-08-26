"""Companion-package capability probe.

Reports whether a companion package (today only ``vaultspec-rag``, which
provides semantic search) is provisioned into a workspace, what provisioning
mode it declares, what version is resolvable, and how that version stands
against core's advisory floor.

The probe is deliberately inert. It reads two things: the workspace
``.mcp.json`` entry - a shape *core* renders through
:func:`~vaultspec_core.core.mcps_mode.render_launch_for_mode`, not a shape the
companion authors - and installed-distribution metadata. It imports no
companion module, opens no socket, and calls no companion API, so no companion
request or response schema is on its path and there is nothing for a companion
release to break.

The cost of that inertness is stated plainly rather than papered over: this
reports *provisioning*, not *health*. A companion that is installed, current,
and dead reports as provisioned. Liveness belongs to the companion's own
observability verbs, which are designed to answer while degraded, so
:attr:`CompanionCapability.health_authority` names that command and every
renderer surfaces it instead of guessing.

See ``.vault/adr/2026-08-26-rag-search-exposure-adr.md``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from .collectors_mode import observed_mcp_mode

if TYPE_CHECKING:
    from pathlib import Path

    from ..enums import InstallMode

logger = logging.getLogger(__name__)

#: The companion distribution providing semantic search.
RAG_DISTRIBUTION_NAME = "vaultspec-rag"

#: Core's advisory floor for :data:`RAG_DISTRIBUTION_NAME`.
#:
#: The single rag version literal in the tree. The ``dev`` dependency-group
#: specifier derives from it, so the two cannot disagree.
#:
#: This floor is *core-local by decision*. It is never written into the
#: ``.vaultspec/workspace.json`` per-package map: that map's ``minimum_version``
#: on a distribution's own entry is an input to *that distribution's* skew gate,
#: and rag writes its own entry through core's
#: :func:`~vaultspec_core.core.workspace_mode.write_package_declaration` while
#: preserving the floor it reads back. A floor written there by core would
#: therefore stop being an advisory core renders and become a control that can
#: make rag refuse its own invocation. That is actuation, not observation.
RAG_MINIMUM_VERSION = "0.4.4"

#: The companion command that authoritatively answers liveness and index health.
#:
#: rag exempts its observability verbs from the release gate that fails every
#: data-plane call closed, because they are how an operator observes and
#: resolves a mismatch. That makes this the one surface designed to answer under
#: exactly the degraded conditions where a core-side probe would be least
#: trustworthy.
RAG_HEALTH_AUTHORITY = "vaultspec-rag server doctor"


class CompanionSignal(StrEnum):
    """Observed provisioning state of a companion package.

    The states are ordered by how much the probe managed to learn, and each
    axis degrades independently so a partial answer is never reported as a
    total one.

    Members:
        ABSENT: No companion entry in the workspace ``.mcp.json``. The
            companion is not provisioned here; this is an ordinary state, not
            a fault.
        DECLARED: A companion entry is provisioned, but no version is
            resolvable from this environment. This is the *expected* state in
            tool mode, where the companion runs through an ephemeral
            ``uvx --from`` invocation and deliberately never enters the
            governed project's dependency set. It is not a warning.
        PRESENT: Provisioned, version resolved, and at or above core's
            advisory floor.
        BELOW_FLOOR: Provisioned and version resolved, but below core's
            advisory floor. Advisory only - it never refuses a core operation.
    """

    ABSENT = "absent"
    DECLARED = "declared"
    PRESENT = "present"
    BELOW_FLOOR = "below_floor"


@dataclass(frozen=True)
class CompanionCapability:
    """One companion package's observed provisioning state.

    Attributes:
        package: The companion distribution name probed.
        signal: The observed :class:`CompanionSignal`.
        mode: The provisioning mode the deployed launch is shaped for, or
            ``None`` when there is no entry or its shape is unrecognized.
        version: The resolved distribution version, or ``None`` when this
            environment cannot see one.
        floor: Core's advisory floor for this package.
        health_authority: The companion command that answers liveness, which
            this probe deliberately does not.
    """

    package: str
    signal: CompanionSignal
    mode: InstallMode | None
    version: str | None
    floor: str
    health_authority: str

    @property
    def provisioned(self) -> bool:
        """Whether a companion entry is provisioned in this workspace."""
        return self.signal is not CompanionSignal.ABSENT

    @property
    def reports_health(self) -> bool:
        """Whether this probe speaks to liveness. Always ``False``, by design.

        Exposed so a renderer asserts the boundary rather than remembering it.
        """
        return False


def _resolve_version(package: str) -> str | None:
    """Return *package*'s installed version, or ``None`` when unresolvable.

    Args:
        package: Distribution name to look up.

    Returns:
        The version string, or ``None`` when the distribution is not installed
        in this environment - the ordinary case in tool mode.
    """
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version(package)
    except PackageNotFoundError:
        return None


def _below_floor(running: str, floor: str) -> bool:
    """Return whether *running* is strictly below *floor*.

    Unparseable versions impose no constraint. This needs an explicit guard
    rather than a bare ``try``: ``parse_version_tuple`` does not raise on a
    string with no leading numeric segment - it returns the empty tuple, which
    compares strictly below every real version. Relying on the exception alone
    would therefore report unrecognized version text as *below floor*, a false
    alarm on the one axis where a false alarm is most corrosive, since an
    advisory nobody trusts is worse than no advisory.

    Args:
        running: The resolved running version.
        floor: The advisory floor.

    Returns:
        ``True`` only when both parse to a non-empty tuple and *running* is
        strictly below *floor*.
    """
    from ..helpers import parse_version_tuple

    try:
        running_parts = parse_version_tuple(running)
        floor_parts = parse_version_tuple(floor)
    except ValueError:
        return False
    if not running_parts or not floor_parts:
        return False
    return running_parts < floor_parts


def _has_entry(target: Path, package: str) -> bool:
    """Return whether ``.mcp.json`` carries an entry named *package*.

    Separate from
    :func:`~vaultspec_core.core.diagnosis.collectors_mode.observed_mcp_mode`
    because that returns ``None`` both for "no entry" and for "entry whose
    launch shape is unrecognized". Only the first means absent, and conflating
    them would report a drifted-but-real provisioning as no provisioning at all.

    Args:
        target: Workspace root directory.
        package: Distribution name whose entry to look for.

    Returns:
        ``True`` when an entry of that name exists.
    """
    from .collectors_config import read_mcp_servers

    servers = read_mcp_servers(target / ".mcp.json")
    return servers is not None and package in servers


def _entry_shape_mode(target: Path, package: str) -> InstallMode | None:
    """Infer *package*'s mode from its launch command token alone.

    A deliberate fallback behind the exact comparator, needed because the exact
    one cannot recognize a companion's real tool-mode launch. ``observed_mcp_mode``
    re-renders the expected argv through ``render_launch_for_mode`` without a
    ``tool_spec``, so it expects ``uvx --from <package>``; a companion that
    provisions an extra - rag declares ``vaultspec-rag[mcp]`` - deploys
    ``uvx --from vaultspec-rag[mcp]`` and never matches. Left at that, the most
    common real rag deployment would report an unknown mode.

    The rule here is structural and carries no per-package knowledge: ``uvx``
    launches tool mode, ``uv`` launches dependency mode. That is the same
    two-shape model ``render_launch_for_mode`` encodes, read from the command
    token instead of the whole argv, so it degrades to a coarser answer rather
    than a wrong one and needs no table of anyone's extras.

    The exact comparator is still tried first, so a byte-exact match keeps its
    stronger verdict and this never weakens an answer that was already precise.

    Args:
        target: Workspace root directory.
        package: Distribution name whose entry to inspect.

    Returns:
        The inferred mode, or ``None`` when there is no entry or its command
        token is neither launcher.
    """
    from ..enums import InstallMode
    from .collectors_config import read_mcp_servers

    servers = read_mcp_servers(target / ".mcp.json")
    if servers is None:
        return None
    entry = servers.get(package)
    if not isinstance(entry, dict):
        return None
    command = entry.get("command")  # pyright: ignore[reportUnknownMemberType]
    if command == "uvx":
        return InstallMode.TOOL
    if command == "uv":
        return InstallMode.DEPENDENCY
    return None


def collect_companion_capability(
    target: Path,
    package: str = RAG_DISTRIBUTION_NAME,
    floor: str = RAG_MINIMUM_VERSION,
    health_authority: str = RAG_HEALTH_AUTHORITY,
) -> CompanionCapability:
    """Probe *package*'s provisioning state in *target*.

    Resolves two independent axes and stops: whether the workspace
    ``.mcp.json`` carries an entry for *package* and what mode its launch is
    shaped for, via the shared
    :func:`~vaultspec_core.core.diagnosis.collectors_mode.observed_mcp_mode`
    comparator; and whether this environment can see an installed version.
    Neither axis can fail the call - each degrades to its own reported state.

    No companion module is imported, no socket is opened, and no companion API
    is called.

    Args:
        target: Workspace root directory.
        package: Companion distribution name to probe.
        floor: Core's advisory floor for *package*.
        health_authority: The companion command that answers liveness.

    Returns:
        The observed :class:`CompanionCapability`.
    """
    mode = observed_mcp_mode(target, package) or _entry_shape_mode(target, package)
    entry_present = mode is not None or _has_entry(target, package)

    if not entry_present:
        return CompanionCapability(
            package=package,
            signal=CompanionSignal.ABSENT,
            mode=None,
            version=None,
            floor=floor,
            health_authority=health_authority,
        )

    running = _resolve_version(package)
    if running is None:
        signal = CompanionSignal.DECLARED
    elif _below_floor(running, floor):
        signal = CompanionSignal.BELOW_FLOOR
    else:
        signal = CompanionSignal.PRESENT

    return CompanionCapability(
        package=package,
        signal=signal,
        mode=mode,
        version=running,
        floor=floor,
        health_authority=health_authority,
    )
