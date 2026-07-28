"""Install-mode coherence and version-floor collectors.

Infers the install mode a deployed MCP launch command is shaped for, compares
a package's declared mode against its provisioned artifacts, evaluates a
package's committed version floor, and surfaces stale package-bundled MCP
seed definitions. All imports from ``core.*`` modules are deferred inside
function bodies to prevent import cycles.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .collectors_config import _read_mcp_servers
from .collectors_precommit import _observed_precommit_mode
from .signals import ModeMismatchSignal, VersionFloorSignal

if TYPE_CHECKING:
    from ..enums import InstallMode

logger = logging.getLogger(__name__)


#: The pre-``--no-sync`` dependency-mode MCP launch shape. Deployed workspaces
#: seeded before the guard was introduced still carry this exact byte sequence, so
#: :func:`_observed_mcp_mode` recognizes it as a bounded, explicit legacy
#: candidate rather than silently reporting ``None`` for every not-yet-refreshed
#: dependency-mode workspace. It is derived from the current renderer's args
#: with the ``--no-sync`` element removed, so it can never drift into a second
#: hand-maintained launch copy: only this one historical shape is recognized,
#: and the mismatch it produces against the current declaration surfaces as
#: ordinary drift, remediated by ``spec mcps sync --force`` or
#: ``install --upgrade`` through the existing force-managed seam.
def _legacy_dependency_args(module: str) -> list[str]:
    from ..enums import InstallMode
    from ..mcps import render_launch_for_mode

    _, current_args = render_launch_for_mode(InstallMode.DEPENDENCY, "", module)
    return [arg for arg in current_args if arg != "--no-sync"]


def _launch_module(args: list[Any]) -> str | None:
    """Return the runnable module a deployed launch argv names after ``-m``.

    Args:
        args: The ``args`` list of a deployed MCP server entry.

    Returns:
        The module name, or ``None`` when the argv carries no ``-m`` token, the
        token is last, or the value after it is not a string.
    """
    if "-m" not in args:
        return None
    module_index = args.index("-m") + 1
    if module_index >= len(args):
        return None
    module = args[module_index]
    return module if isinstance(module, str) else None


def _observed_mcp_mode(target: Path, package: str | None = None) -> InstallMode | None:
    """Infer the install mode *package*'s deployed MCP launch command is shaped for.

    Reads ``.mcp.json`` and matches *package*'s server entry (the server name is
    the distribution name) against the concrete launch each mode renders
    (dependency mode launches through ``uv run --no-sync``, tool mode through
    ``uvx``). The runnable module is recovered from the deployed ``args`` (the
    token after ``-m``) and the two candidate shapes are reconstructed through
    the renderer's own :func:`~vaultspec_core.core.mcps.render_launch_for_mode`,
    so this matches against the single launch comparator rather than a second
    hardcoded copy and works for any package's module without a per-package
    table.

    A deployed entry shaped like the pre-``--no-sync`` legacy dependency launch
    (``uv run python -m <module>``, no guard) also matches
    :attr:`~vaultspec_core.core.enums.InstallMode.DEPENDENCY`
    (:data:`_legacy_dependency_args`), so mode inference and the mode-mismatch
    signal do not regress to ``None`` on workspaces seeded before the guard was
    introduced; the byte difference between the legacy and current shapes then
    reports as ordinary drift with a fix hint pointing at
    ``spec mcps sync --force`` or ``install --upgrade``.

    Args:
        target: Workspace root directory.
        package: Distribution name whose server entry to read; ``None`` means
            ``vaultspec-core``. The server name in ``.mcp.json`` is this name.

    Returns:
        The matching :class:`~vaultspec_core.core.enums.InstallMode`, or ``None``
        when there is no config, no matching server entry, the module cannot be
        recovered, or the entry matches neither rendered nor legacy launch shape.
    """
    from ..enums import InstallMode
    from ..mcps import render_launch_for_mode
    from ..workspace_mode import CORE_DISTRIBUTION_NAME

    pkg = package if package is not None else CORE_DISTRIBUTION_NAME

    servers = _read_mcp_servers(target / ".mcp.json")
    if servers is None:
        return None
    entry = servers.get(pkg)
    if not isinstance(entry, dict):
        return None

    command = entry.get("command")
    args = entry.get("args")
    module = _launch_module(args) if isinstance(args, list) else None
    if module is None:
        return None

    for mode in (InstallMode.TOOL, InstallMode.DEPENDENCY):
        mode_command, mode_args = render_launch_for_mode(mode, pkg, module)
        if command == mode_command and args == mode_args:
            return mode

    if command == "uv" and args == _legacy_dependency_args(module):
        return InstallMode.DEPENDENCY

    return None


def collect_mode_mismatch_state(
    target: Path, package: str | None = None
) -> ModeMismatchSignal:
    """Compare *package*'s persisted install mode against its observed artifacts.

    Reads *package*'s own entry in the committed ``.vaultspec/workspace.json``
    declaration and holds the mode it names against the shape of that package's
    provisioned artifacts: for core, the canonical pre-commit hook entries and
    the ``.mcp.json`` launch command; for a companion package, only its own MCP
    launch. When a deployed artifact is shaped for a mode other than the declared
    one - a ``uv run`` hook entry or a non-``uvx`` MCP command in a workspace
    whose declaration names tool mode, or the reverse - the workspace is flagged
    :attr:`~vaultspec_core.core.diagnosis.signals.ModeMismatchSignal.MISMATCH`
    with the fix hint pointing at ``install --upgrade`` or an explicit
    ``--mode`` re-run.

    The declared mode is compared through
    :func:`~vaultspec_core.core.enums.render_mode`, not raw, because that is the
    mode the artifacts actually render as: a declared-``dev`` package renders
    byte-identically to ``dependency``, so a ``dev`` declaration against
    dependency-shaped artifacts is coherent, not a mismatch. Without this
    collapse every ``dev``-mode workspace would falsely flag, since no artifact
    ever carries a distinct ``dev`` shape.

    A package with no persisted entry is
    :attr:`~vaultspec_core.core.diagnosis.signals.ModeMismatchSignal.UNKNOWN`:
    it predates the ``install-mode`` decision (or is not provisioned), so there
    is no declared mode to hold its artifacts against and this is not a warning.
    Everything coherent - or a declared package whose artifacts cannot be read -
    is :attr:`~vaultspec_core.core.diagnosis.signals.ModeMismatchSignal.CLEAN`.

    Args:
        target: Workspace root directory.
        package: Distribution name whose mode coherence to assess; ``None`` means
            ``vaultspec-core``.

    Returns:
        The observed
        :class:`~vaultspec_core.core.diagnosis.signals.ModeMismatchSignal`.

    Raises:
        VaultSpecError: If the declaration exists but is malformed (propagated
            from
            :func:`~vaultspec_core.core.workspace_mode.read_package_declaration`).
    """
    from ..enums import render_mode
    from ..workspace_mode import CORE_DISTRIBUTION_NAME, read_package_declaration

    pkg = package if package is not None else CORE_DISTRIBUTION_NAME
    declaration = read_package_declaration(target, pkg)
    if declaration is None:
        return ModeMismatchSignal.UNKNOWN

    declared = render_mode(declaration.install_mode)
    observed = {
        mode
        for mode in (
            _observed_precommit_mode(target, pkg),
            _observed_mcp_mode(target, pkg),
        )
        if mode is not None
    }
    if any(mode != declared for mode in observed):
        return ModeMismatchSignal.MISMATCH
    return ModeMismatchSignal.CLEAN


def collect_version_floor_state(
    target: Path, package: str | None = None
) -> tuple[VersionFloorSignal, str, str]:
    """Evaluate *package*'s committed floor constraint for the doctor's read-only view.

    Runs the shared :func:`~vaultspec_core.core.workspace_mode.evaluate_version_floor`
    comparator - the same one the resolver's refuse-and-tell path uses - so the
    doctor reports exactly the condition install and sync refuse on. The running
    version tested is *package*'s own installed version, and the floor is
    *package*'s own entry in the shared map, so a companion package's floor is
    diagnosed against its own release rather than core's. Unlike the enforcement
    path, this never raises: a corrupt declaration or an unreadable version is
    treated as "no constraint" so the read-only doctor surface stays crash-free.

    Args:
        target: Workspace root directory.
        package: Distribution name whose floor to evaluate; ``None`` means
            ``vaultspec-core``.

    Returns:
        ``(signal, running_version, minimum_version)``. When the running
        version is below the floor the signal is
        :attr:`~vaultspec_core.core.diagnosis.signals.VersionFloorSignal.BELOW`
        and the two version strings are populated; otherwise the signal is
        :attr:`~vaultspec_core.core.diagnosis.signals.VersionFloorSignal.OK`
        with empty strings.
    """
    from importlib.metadata import version as pkg_version

    from ..exceptions import VaultSpecError
    from ..workspace_mode import CORE_DISTRIBUTION_NAME, evaluate_version_floor

    pkg = package if package is not None else CORE_DISTRIBUTION_NAME

    try:
        running = pkg_version(pkg)
    except Exception:
        logger.debug("Could not determine running version for floor state")
        return VersionFloorSignal.OK, "", ""

    try:
        violation = evaluate_version_floor(target, running, package=pkg)
    except VaultSpecError:
        logger.debug("Could not read declaration for floor state", exc_info=True)
        return VersionFloorSignal.OK, "", ""

    if violation is None:
        return VersionFloorSignal.OK, "", ""

    running_v, floor = violation
    return VersionFloorSignal.BELOW, running_v, floor


def observed_mcp_mode(target: Path, package: str | None = None) -> InstallMode | None:
    """Public accessor for the deployed MCP entry's observed install mode.

    Companion packages (vaultspec-rag's upgrade inference and mode-flip
    detection) consume this observation; the private helper stays the
    internal implementation.

    Args:
        target: Workspace root directory.
        package: Distribution name whose server entry to read; ``None``
            means ``vaultspec-core``.

    Returns:
        The :class:`~vaultspec_core.core.enums.InstallMode` the deployed
        entry is shaped for, or ``None`` when unobservable.
    """
    return _observed_mcp_mode(target, package)


def collect_stale_seed_definitions(target: Path) -> list[str]:
    """Return package-bundled MCP seed definitions still in a static shape.

    A ``.builtin.json`` definition under ``.vaultspec/mcps/`` is seeded by its
    owning package's installer and, since the mode-aware provisioning model,
    always carries the mode-neutral launch tokens. A builtin seed whose
    ``command`` is a concrete string instead of the token predates that model:
    it bypasses the launch renderer entirely, so no core-side sync or upgrade
    can converge it - only re-running the owning package's installer refreshes
    the seed. The doctor surfaces these so the stale state is visible where
    operators look, rather than only in installer logs.

    Custom user definitions (plain ``.json``) are the user's own content and
    are never reported here.

    Args:
        target: Workspace root directory.

    Returns:
        Sorted server names of stale package-bundled seed definitions; empty
        when every builtin seed is mode-neutral or none exist.
    """
    from ..mcps import _MODE_COMMAND_TOKEN, _server_name

    mcps_dir = target / ".vaultspec" / "mcps"
    if not mcps_dir.exists():
        return []

    stale: list[str] = []
    for path in sorted(mcps_dir.glob("*.builtin.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Cannot read MCP seed definition %s: %s", path, exc)
            continue
        if isinstance(raw, dict) and raw.get("command") != _MODE_COMMAND_TOKEN:
            stale.append(_server_name(path.name))
    return sorted(stale)
