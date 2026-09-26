"""Resolve and persist the workspace's provisioning mode across install/upgrade.

Centralizes the small set of helpers that stamp manifest schema versions
without downgrading them, persist a resolved
:class:`~vaultspec_core.core.enums.InstallMode` to the committed workspace
declaration, and infer the mode for a legacy workspace being upgraded
(ADR Q6).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .enums import InstallMode
from .helpers import package_version, parse_version_tuple
from .workspace_mode import resolve_install_mode

if TYPE_CHECKING:
    from collections.abc import Callable

    from .manifest import ManifestData
    from .workspace_mode import ResolvedMode

__all__ = ["infer_upgrade_mode", "write_mode_declaration"]


def stamp_manifest_version_no_downgrade(mdata: ManifestData) -> None:
    """Set ``mdata.vaultspec_version`` to the running package version.

    Never downgrade: a registered migration whose ``target_version``
    exceeds the running package's version may have just bumped the
    manifest above the running release, and rewriting it back would
    silently re-flag the migration as pending on the next run.
    """
    running = package_version()
    if parse_version_tuple(running) > parse_version_tuple(mdata.vaultspec_version):
        mdata.vaultspec_version = running


def fresh_install_schema_version() -> str:
    """Return the manifest version a freshly-installed workspace conforms to.

    A fresh install writes the current on-disk schema, so it must not
    leave any registered migration pending. When a migration targets a
    version above the running package - the normal state while a schema
    change and its migration ship together, before the release that
    carries them - the fresh manifest is stamped at that target so the
    migration is correctly seen as already satisfied.
    """
    from ..migrations import REGISTRY

    candidates = [package_version(), *(m.target_version for m in REGISTRY)]
    return max(candidates, key=parse_version_tuple)


def persist_resolved_mode(path: Path, mdata: ManifestData, mode: InstallMode) -> None:
    """Persist *mode* to the committed declaration and echo it into *mdata*.

    Writes the shared source of truth (``.vaultspec/workspace.json`` via
    :func:`~vaultspec_core.core.workspace_mode.write_workspace_declaration`) and
    mirrors the resolved value into the gitignored per-machine manifest for
    local bookkeeping. An existing floor constraint
    (``minimum_vaultspec_version``) is preserved rather than dropped, since the
    provisioning mode and the floor are independent axes of the same
    declaration.

    The declaration writer takes its own advisory lock, so this function must
    not be called from within the manifest lock; *mdata* is mutated in place and
    persisted by the caller's own :func:`write_manifest_data` cycle.

    Invariant: callers run this only after
    :func:`~vaultspec_core.core.workspace_mode.resolve_install_mode`, which reads
    and validates any persisted declaration fail-fast. The re-read here is
    therefore expected to succeed - a corrupt declaration would already have
    aborted the run before any mutation - so this does not reintroduce a
    late-failure window.

    Args:
        path: Workspace root directory.
        mdata: Manifest data to stamp with the resolved mode echo; mutated in
            place, not written here.
        mode: The resolved provisioning mode to persist.
    """
    floor = write_mode_declaration(path, mode)
    mdata.resolved_mode = mode
    mdata.resolved_floor_version = floor


def write_mode_declaration(path: Path, mode: InstallMode) -> str | None:
    """Write core's committed mode entry, preserving its floor and any siblings.

    Reads and writes only ``vaultspec-core``'s own entry in the shared
    per-package map through the per-package helpers, so a companion package's
    entry (for example ``vaultspec-rag``) is never touched when core's mode is
    rewritten. The provisioning mode and the per-package ``minimum_version``
    floor are independent axes of the same entry, so rewriting the mode must
    never drop a floor a prior run recorded. :func:`write_package_declaration`'s
    read-modify-write under the advisory lock is deterministic (sorted keys,
    fixed indent), so re-writing the same mode leaves byte-identical content,
    which is what makes a repeated ``install --upgrade`` idempotent.

    Args:
        path: Workspace root directory.
        mode: The resolved provisioning mode to persist.

    Returns:
        The preserved floor constraint (or ``None``), so a caller echoing the
        declaration into the manifest need not re-read it.
    """
    from .workspace_mode import (
        CORE_DISTRIBUTION_NAME,
        PackageDeclaration,
        read_package_declaration,
        write_package_declaration,
    )

    existing = read_package_declaration(path, CORE_DISTRIBUTION_NAME)
    floor = existing.minimum_version if existing is not None else None
    write_package_declaration(
        path,
        CORE_DISTRIBUTION_NAME,
        PackageDeclaration(install_mode=mode, minimum_version=floor),
    )
    return floor


def infer_upgrade_mode(
    target: Path,
    package: str,
    *,
    launch_is_module_run: Callable[[], bool] | bool,
) -> InstallMode:
    """Infer *package*'s mode for a legacy workspace that declares none.

    Two signals have to agree. Detection says where the workspace's
    ``pyproject.toml`` places the package: a runtime dependency resolves to
    dependency mode, a default dev group to the non-leaking dev mode, and
    nothing detectable leaves tool mode standing. Deployment says how the
    workspace actually launches the package today, which is the evidence the
    caller supplies: ``uv run``-shaped means it launches from the workspace's
    own environment, anything else means it does not.

    A workspace can list a package and still launch it as a global tool, and
    upgrading it to dependency mode on the listing alone would rewrite a
    working deployment into a broken one. So detection only carries when the
    deployed launch already agrees with it.

    Each package supplies its own evidence because each has its own launch
    surface: core reads the shape of its committed pre-commit entries, while
    a package that scaffolds no hooks reads whatever it does own. Passing a
    callable defers that work to the one branch that needs it.

    Args:
        target: Workspace root directory.
        package: The distribution whose mode to infer.
        launch_is_module_run: Whether the workspace's existing launch entry
            for *package* is ``uv run``-shaped, or a callable answering that.

    Returns:
        The inferred mode. Never a declared or requested one: the caller
        checks for those first, because they outrank inference.

    Raises:
        VaultSpecError: Propagated from mode resolution when a persisted
            declaration is malformed.
    """
    detected = resolve_install_mode(target, explicit=None, package=package)
    if detected is InstallMode.TOOL:
        return InstallMode.TOOL
    launched = (
        launch_is_module_run()
        if callable(launch_is_module_run)
        else launch_is_module_run
    )
    return detected if launched else InstallMode.TOOL


def upgrade_mode_with_provenance(
    target: Path, explicit: InstallMode | None
) -> ResolvedMode:
    """Resolve core's provisioning mode for an ``install --upgrade`` (ADR Q6).

    Precedence mirrors provision-time resolution at its top: an explicit
    ``--mode`` flag wins (and is validated for impossible combinations), and an
    already-persisted declaration wins next, so a second upgrade is idempotent
    and a deliberate re-mode is honored. A legacy workspace with neither has its
    mode inferred by :func:`infer_upgrade_mode`, the rule every package shares,
    with core's own deployed evidence: the shape of its canonical hook entries.

    That shape is read through the same ``observed_precommit_mode``
    collector the doctor's mode-mismatch check consumes, so migration and
    diagnosis can never disagree on what a deployed artifact shape means - the
    ``install-mode`` constraint against introducing a second comparator.

    The returned :class:`~vaultspec_core.core.workspace_mode.ResolvedMode`
    carries provenance so the caller can fire the dependency-leak advisory only
    when this upgrade newly *infers* dependency mode for a legacy workspace, not
    when it reads an already-persisted dependency declaration.

    Args:
        target: Workspace root directory.
        explicit: The mode requested via ``--mode``, or ``None``.

    Returns:
        The inferred mode paired with its
        :class:`~vaultspec_core.core.workspace_mode.ModeProvenance`.

    Raises:
        VaultSpecError: Propagated from
            :func:`~vaultspec_core.core.workspace_mode.resolve_install_mode_with_provenance`
            when *explicit* names an impossible combination or a persisted
            declaration is malformed.
    """
    from .workspace_mode import (
        CORE_DISTRIBUTION_NAME,
        ModeProvenance,
        ResolvedMode,
        read_package_declaration,
        resolve_install_mode_with_provenance,
    )

    if explicit is not None:
        return resolve_install_mode_with_provenance(target, explicit=explicit)
    if read_package_declaration(target, CORE_DISTRIBUTION_NAME) is not None:
        return resolve_install_mode_with_provenance(target, explicit=None)

    inferred = infer_upgrade_mode(
        target,
        CORE_DISTRIBUTION_NAME,
        launch_is_module_run=lambda: _hook_entries_are_module_run(target),
    )
    return ResolvedMode(inferred, ModeProvenance.INFERRED)


def _hook_entries_are_module_run(target: Path) -> bool:
    """Return whether *target*'s canonical hook entries launch through ``uv run``.

    Dev and dependency modes render one shape and tool mode renders another,
    so the question is which shape the deployed entries carry, not which mode
    the collector names.
    """
    from .diagnosis.collectors import observed_precommit_mode
    from .precommit import entry_prefix_for_mode

    observed = observed_precommit_mode(target)
    if observed is None:
        return False
    return entry_prefix_for_mode(observed) == entry_prefix_for_mode(
        InstallMode.DEPENDENCY
    )
