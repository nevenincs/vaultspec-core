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

if TYPE_CHECKING:
    from .manifest import ManifestData
    from .workspace_mode import ResolvedMode


def _stamp_manifest_version_no_downgrade(mdata: ManifestData) -> None:
    """Set ``mdata.vaultspec_version`` to the running package version.

    Never downgrade: a registered migration whose ``target_version``
    exceeds the running package's version may have just bumped the
    manifest above the running release, and rewriting it back would
    silently re-flag the migration as pending on the next run.
    """
    running = package_version()
    if parse_version_tuple(running) > parse_version_tuple(mdata.vaultspec_version):
        mdata.vaultspec_version = running


def _fresh_install_schema_version() -> str:
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


def _persist_resolved_mode(path: Path, mdata: ManifestData, mode: InstallMode) -> None:
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
    floor = _write_mode_declaration(path, mode)
    mdata.resolved_mode = mode
    mdata.resolved_floor_version = floor


def _write_mode_declaration(path: Path, mode: InstallMode) -> str | None:
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


def _infer_upgrade_mode(target: Path, explicit: InstallMode | None) -> ResolvedMode:
    """Infer the provisioning mode for an ``install --upgrade`` (ADR Q6).

    Precedence mirrors provision-time resolution at its top: an explicit
    ``--mode`` flag wins (and is validated for impossible combinations), and an
    already-persisted declaration wins next, so a second upgrade is idempotent
    and a deliberate re-mode is honored. A legacy workspace with neither has its
    mode inferred from its own deployed state: dependency mode only when the
    canonical hook entries are ``uv run``-shaped *and* the target's
    ``pyproject.toml`` lists ``vaultspec-core``; tool mode in every other case.

    The hook-shape signal is read through the same ``_observed_precommit_mode``
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
    from .diagnosis.collectors import _observed_precommit_mode
    from .workspace_mode import (
        CORE_DISTRIBUTION_NAME,
        ModeProvenance,
        ResolvedMode,
        read_package_declaration,
        resolve_install_mode,
        resolve_install_mode_with_provenance,
    )

    if explicit is not None:
        return resolve_install_mode_with_provenance(target, explicit=explicit)
    if read_package_declaration(target, CORE_DISTRIBUTION_NAME) is not None:
        return resolve_install_mode_with_provenance(target, explicit=None)

    detected = resolve_install_mode(target, explicit=None)
    observed = _observed_precommit_mode(target)
    if detected is InstallMode.DEPENDENCY and observed is InstallMode.DEPENDENCY:
        return ResolvedMode(InstallMode.DEPENDENCY, ModeProvenance.INFERRED)
    return ResolvedMode(InstallMode.TOOL, ModeProvenance.INFERRED)
