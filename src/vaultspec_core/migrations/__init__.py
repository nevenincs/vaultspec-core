"""Versioned migration registry for vaultspec-managed workspaces.

Schema migrations relocate or rewrite ``.vault/`` content when a new
release of vaultspec-core changes the on-disk shape. Each migration
declares its target release version and exposes an idempotent
``migrate(workspace) -> MigrationResult`` callable. The driver
:func:`run_pending_migrations` reads the workspace manifest, runs every
entry whose ``target_version`` exceeds the manifest's
``vaultspec_version``, then bumps the manifest version on success.

Triggers:

- :func:`vaultspec_core.core.commands.install_run` runs the driver in
  the upgrade branch so explicit upgrades migrate immediately.
- :func:`vaultspec_core.vaultcore.scanner.scan_vault` runs the driver
  lazily so any vault command (e.g. ``vault add``,
  ``vault feature index``) migrates a stale workspace before it acts.
- The ``vaultspec-core migrations`` CLI subcommand exposes
  ``status`` and ``run`` for explicit operator control.

A migration whose body raises bubbles the exception up and prevents
the manifest version bump. The next invocation re-attempts from the
same starting version, so partial failures do not leave the workspace
half-migrated from the registry's bookkeeping perspective.

See also:
    :class:`vaultspec_core.core.manifest.ManifestData` for the
    ``vaultspec_version`` field that anchors the comparison.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from ..core.helpers import parse_version_tuple
from ..core.manifest import read_manifest_data, write_manifest_data

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

__all__ = [
    "MIGRATION_LOGGER",
    "REGISTRY",
    "Migration",
    "MigrationResult",
    "MigrationStatus",
    "list_pending",
    "migration_status",
    "reset_workspace_cache",
    "run_pending_migrations",
]

MIGRATION_LOGGER = "vaultspec_core.migrations"
logger = logging.getLogger(MIGRATION_LOGGER)


class MigrationStatus(Enum):
    """High-level migration state for a workspace.

    Attributes:
        UP_TO_DATE: Manifest version covers every registered migration.
        PENDING: One or more registered migrations have a target version
            higher than the manifest's recorded ``vaultspec_version``.
        UNKNOWN: The workspace has no manifest (not installed) or the
            manifest is unreadable.
    """

    UP_TO_DATE = "up_to_date"
    PENDING = "pending"
    UNKNOWN = "unknown"


@dataclass
class MigrationResult:
    """Outcome of a single migration run.

    Attributes:
        name: Short identifier of the migration that produced this
            result. Matches the ``Migration.name`` field and the
            module-name slug.
        target_version: Release version that introduced the schema
            change, copied from :attr:`Migration.target_version`.
        summary: One-line operator-facing description of what the
            migration did, e.g. ``"relocated 12 feature indexes"``.
        counts: Free-form integer counters for additional structured
            detail (e.g. ``{"moved": 12, "skipped": 0}``).
    """

    name: str
    target_version: str
    summary: str
    counts: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class Migration:
    """A single registered schema migration.

    Migration ``migrate`` callables must be idempotent: running them on
    an already-migrated workspace is required to be a true no-op (no
    filesystem mutation, no error, the returned :class:`MigrationResult`
    reports zero work).

    Attributes:
        target_version: Release version that introduced the schema
            change. Strict greater-than comparison against
            :attr:`vaultspec_core.core.manifest.ManifestData.vaultspec_version`
            decides whether the migration runs.
        name: Stable short identifier matching the module slug.
        migrate: Callable that performs the migration. Receives the
            workspace root path and returns a :class:`MigrationResult`.
    """

    target_version: str
    name: str
    migrate: Callable[[Path], MigrationResult]


_workspace_cache_lock = threading.Lock()
_workspace_cache: dict[Path, tuple[int, ...]] = {}


def reset_workspace_cache() -> None:
    """Drop the per-process cache of recently-checked workspaces.

    The lazy trigger inside
    :func:`vaultspec_core.vaultcore.scanner.scan_vault` records each
    workspace it has already vetted so the manifest read does not
    repeat for every scan within a single CLI invocation. Tests need
    a way to clear that cache between fixtures so each scenario
    starts from a clean slate.
    """
    with _workspace_cache_lock:
        _workspace_cache.clear()


def _build_registry() -> list[Migration]:
    """Assemble the ordered registry from the per-version migration modules.

    Imports each module lazily and returns the migrations sorted by
    parsed target version. Lazy imports keep the registry module
    cheap to import in code paths that never run migrations.
    """
    from .m_0_1_17_index_subfolder import MIGRATION as M_INDEX_SUBFOLDER

    entries: list[Migration] = [M_INDEX_SUBFOLDER]
    return sorted(entries, key=lambda m: parse_version_tuple(m.target_version))


REGISTRY: list[Migration] = _build_registry()


def list_pending(workspace: Path) -> list[Migration]:
    """Return every registered migration with a target above the manifest.

    Reads the workspace manifest and filters
    :data:`REGISTRY` to entries whose ``target_version`` is strictly
    greater than the manifest's ``vaultspec_version``. A workspace
    without a manifest (no ``providers.json``) is treated as a
    not-installed case and produces an empty list; the registry only
    runs against an installed workspace.

    Args:
        workspace: Workspace root directory.

    Returns:
        List of pending :class:`Migration` instances in version order.
    """
    manifest = read_manifest_data(workspace)
    if not manifest.vaultspec_version:
        return []
    current = parse_version_tuple(manifest.vaultspec_version)
    return [m for m in REGISTRY if parse_version_tuple(m.target_version) > current]


def migration_status(workspace: Path) -> tuple[MigrationStatus, list[str]]:
    """Summarise the registry state for *workspace*.

    Args:
        workspace: Workspace root directory.

    Returns:
        Two-tuple ``(status, names)`` where *status* is
        :class:`MigrationStatus` and *names* is the list of pending
        migration names (empty when ``status`` is
        :attr:`MigrationStatus.UP_TO_DATE` or
        :attr:`MigrationStatus.UNKNOWN`).
    """
    manifest = read_manifest_data(workspace)
    if not manifest.vaultspec_version:
        return MigrationStatus.UNKNOWN, []
    pending = list_pending(workspace)
    if not pending:
        return MigrationStatus.UP_TO_DATE, []
    return MigrationStatus.PENDING, [m.name for m in pending]


def _running_version() -> str:
    """Return the running ``vaultspec-core`` package version.

    Wraps :func:`importlib.metadata.version` and falls back to
    ``"unknown"`` so the driver still completes when running from a
    development tree without metadata.
    """
    try:
        from importlib.metadata import version

        return version("vaultspec-core")
    except Exception:
        return "unknown"


def run_pending_migrations(
    workspace: Path,
    *,
    use_cache: bool = False,
) -> list[MigrationResult]:
    """Run every registered migration whose target exceeds the manifest version.

    The driver reads :class:`vaultspec_core.core.manifest.ManifestData`,
    parses both the manifest and target versions via
    :func:`vaultspec_core.core.helpers.parse_version_tuple`, runs each
    pending migration in version order, then bumps
    :attr:`ManifestData.vaultspec_version` to the running package
    version on success. A migration that raises propagates the
    exception unchanged and prevents the version bump, so the next
    call re-attempts from the same starting version.

    Args:
        workspace: Workspace root directory.
        use_cache: When ``True`` (the lazy-trigger path), short-circuits
            on a per-process cache of workspaces previously seen
            up-to-date. Explicit triggers (CLI ``migrations run``,
            ``install --upgrade``) pass ``False`` so they always
            consult the manifest.

    Returns:
        Per-migration :class:`MigrationResult` entries, in execution
        order. Empty when the workspace has no manifest or every
        registered migration is already covered.
    """
    cached_version: tuple[int, ...] | None = None
    if use_cache:
        with _workspace_cache_lock:
            cached_version = _workspace_cache.get(workspace)

    if cached_version is not None and not any(
        parse_version_tuple(m.target_version) > cached_version for m in REGISTRY
    ):
        return []

    manifest = read_manifest_data(workspace)
    if not manifest.vaultspec_version:
        return []

    current = parse_version_tuple(manifest.vaultspec_version)
    pending = [m for m in REGISTRY if parse_version_tuple(m.target_version) > current]
    if not pending:
        if use_cache:
            with _workspace_cache_lock:
                _workspace_cache[workspace] = current
        return []

    results: list[MigrationResult] = []
    for migration in pending:
        logger.info(
            "Running migration %s (target_version=%s)",
            migration.name,
            migration.target_version,
        )
        result = migration.migrate(workspace)
        logger.info("vaultspec migration: %s", result.summary)
        results.append(result)

    # Bump to whichever is higher: the running package version, or the
    # highest-target migration we just applied. The latter case only
    # arises in tests that synthesise migrations whose target exceeds
    # the running version; the former is the production path where
    # every released migration's target is <= the running version.
    running = _running_version()
    running_parts = parse_version_tuple(running)
    highest_pending_parts = max(
        (parse_version_tuple(m.target_version) for m in pending),
        default=(),
    )
    new_version = (
        running
        if running_parts >= highest_pending_parts
        else pending[-1].target_version
    )

    fresh = read_manifest_data(workspace)
    fresh.vaultspec_version = new_version
    write_manifest_data(workspace, fresh)

    if use_cache:
        with _workspace_cache_lock:
            _workspace_cache[workspace] = parse_version_tuple(new_version)

    return results
