"""Dataclasses aggregating diagnostic signals for providers and workspaces.

The :func:`diagnose` orchestrator drives layered signal collection, delegating
to the individual collectors in :mod:`.collectors`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from ..enums import InstallMode, Tool
from .signals import (
    BuiltinVersionSignal,
    ConfigSignal,
    ContentSignal,
    FrameworkSignal,
    GitattributesSignal,
    GitignoreSignal,
    ManifestEntrySignal,
    ModeMismatchSignal,
    PrecommitSignal,
    ProviderDirSignal,
    RenameIntegritySignal,
    VaultContentSignal,
    VersionFloorSignal,
)

logger = logging.getLogger(__name__)


@dataclass
class PackageModeDiagnosis:
    """Per-package install-mode and version-floor diagnosis.

    One entry per distribution declared in the shared
    ``.vaultspec/workspace.json`` map, so the doctor can render an install-mode
    row (and, when a floor is violated, a version-floor row) for each provisioned
    package independently rather than only for core. A mixed configuration (core
    in one mode, a companion package in another) produces one of these per
    package, each read against that package's own declared entry and its own
    observed artifacts.

    Args:
        package: The canonicalized distribution name.
        declared_mode: The mode this package's map entry declares. Kept distinct
            from the mode its artifacts render as (``dev`` renders like
            ``dependency``) so the doctor row can label the honest declared
            value.
        mode_mismatch: Coherence between the declared mode and the observed
            artifact shapes for this package.
        version_floor: State of this package's running version against its own
            declared floor.
        version_floor_running: Running version string, populated only when
            ``version_floor`` is ``BELOW``.
        version_floor_minimum: Declared floor string, populated only when
            ``version_floor`` is ``BELOW``.
    """

    package: str
    declared_mode: InstallMode
    mode_mismatch: ModeMismatchSignal
    version_floor: VersionFloorSignal
    version_floor_running: str = ""
    version_floor_minimum: str = ""


@dataclass
class ProviderDiagnosis:
    """Collected diagnostic signals for a single provider.

    Args:
        tool: The :class:`~vaultspec_core.core.enums.Tool` being diagnosed.
        dir_state: Observed state of the provider directory.
        manifest_entry: Coherence between directory and manifest.
        content: Per-resource :class:`ContentSignal` map.
        config: State of the provider's root configuration.
    """

    tool: Tool
    dir_state: ProviderDirSignal
    manifest_entry: ManifestEntrySignal
    content: dict[str, ContentSignal] = field(default_factory=dict)
    # Neutral by default because framework-only and corrupted-framework
    # diagnosis paths do not collect provider config state. Callers that
    # actually inspect configs must pass the collected signal explicitly.
    config: ConfigSignal = ConfigSignal.OK


@dataclass
class WorkspaceDiagnosis:
    """Top-level diagnosis aggregating framework and provider states.

    Args:
        framework: Observed state of the vaultspec framework directory.
        providers: Per-tool :class:`ProviderDiagnosis` map.
        builtin_version: Version state of built-in resource snapshots.
        gitignore: Observed state of gitignore entries.
        migration_status: Schema-migration status string. ``"up_to_date"``
            when the manifest version covers every registered migration,
            ``"pending"`` when one or more migrations have a target
            version above the manifest, ``"unknown"`` when the workspace
            has no manifest.
        pending_migrations: List of pending migration names; empty
            unless ``migration_status`` is ``"pending"``.
        vault_content: Read-only generated annotation state for ``.vault/``.
            vault_annotation_count: Count of markdown documents containing
            generated template annotations.
        vault_unreadable_count: Count of unreadable markdown documents skipped
            by the annotation probe.
        rename_integrity: Observed state of name/filename mismatches.
        rename_mismatch_count: Count of name/filename mismatches.
        mode_mismatch: Coherence between core's persisted install-mode
            declaration and the shape of core's provisioned hook and MCP
            artifacts. This is core's own view, kept for the resolver's install
            and sync plans; the per-package ``packages`` map below carries the
            same axis for every declared package including core.
        version_floor: State of core's running version against core's committed
            floor constraint.
        version_floor_running: Running version string, populated only when
            ``version_floor`` is ``BELOW``.
        version_floor_minimum: Declared floor string, populated only when
            ``version_floor`` is ``BELOW``.
        stale_mcp_seeds: Server names of package-bundled MCP seed definitions
            still in a static pre-mode shape; core cannot refresh these, only
            the owning package's installer can.
        packages: Per-package install-mode and version-floor diagnosis, one
            :class:`PackageModeDiagnosis` per distribution declared in the shared
            workspace map, keyed by canonicalized distribution name. Empty when
            no ``workspace.json`` declaration exists. Drives the doctor's
            per-package install-mode and version-floor rows.
        divergent_projections: Workspace-relative paths of projected provider
            files whose on-disk content differs from what the sync engine would
            write. Populated only when ``framework`` is
            :attr:`~vaultspec_core.core.diagnosis.signals.FrameworkSignal.ADOPTABLE`,
            where it names the content an adopting run would destroy.
    """

    framework: FrameworkSignal
    providers: dict[Tool, ProviderDiagnosis] = field(default_factory=dict)
    builtin_version: BuiltinVersionSignal = BuiltinVersionSignal.NO_SNAPSHOTS
    gitignore: GitignoreSignal = GitignoreSignal.NO_FILE
    gitattributes: GitattributesSignal = GitattributesSignal.NO_FILE
    mcp: ConfigSignal = ConfigSignal.MISSING
    precommit: PrecommitSignal = PrecommitSignal.NO_FILE
    stale_mcp_seeds: list[str] = field(default_factory=list)
    migration_status: str = "up_to_date"
    pending_migrations: list[str] = field(default_factory=list)
    vault_content: VaultContentSignal = VaultContentSignal.NO_VAULT
    vault_annotation_count: int = 0
    vault_unreadable_count: int = 0
    rename_integrity: RenameIntegritySignal = RenameIntegritySignal.CLEAN
    rename_mismatch_count: int = 0
    mode_mismatch: ModeMismatchSignal = ModeMismatchSignal.CLEAN
    version_floor: VersionFloorSignal = VersionFloorSignal.OK
    version_floor_running: str = ""
    version_floor_minimum: str = ""
    packages: dict[str, PackageModeDiagnosis] = field(default_factory=dict)
    divergent_projections: list[str] = field(default_factory=list)


def diagnose(target: Path, *, scope: str = "full") -> WorkspaceDiagnosis:
    """Run layered diagnostic collection against a workspace.

    Args:
        target: Workspace root directory to diagnose.
        scope: Collection depth - ``"full"`` runs all collectors (doctor
            command), ``"framework"`` runs only framework presence and manifest
            coherence (install), ``"sync"`` adds provider dir, config, and
            gitignore checks.

    Returns:
        Populated :class:`WorkspaceDiagnosis` instance.
    """
    valid_scopes = frozenset({"full", "framework", "sync"})
    if scope not in valid_scopes:
        raise ValueError(
            f"Invalid scope '{scope}'. Valid: {', '.join(sorted(valid_scopes))}"
        )

    from ..enums import Tool
    from .collectors import (
        collect_builtin_version_state,
        collect_config_state,
        collect_content_integrity,
        collect_divergent_projections,
        collect_framework_presence,
        collect_gitattributes_state,
        collect_gitignore_state,
        collect_manifest_coherence,
        collect_mcp_config_state,
        collect_mode_mismatch_state,
        collect_precommit_state,
        collect_provider_dir_state,
        collect_rename_integrity,
        collect_stale_seed_definitions,
        collect_vault_content_state,
        collect_version_floor_state,
    )

    # Layer 1: always collected
    try:
        framework = collect_framework_presence(target)
    except Exception:
        logger.warning("Framework presence collector failed", exc_info=True)
        framework = FrameworkSignal.MISSING

    try:
        gitignore = collect_gitignore_state(target)
    except Exception:
        logger.warning("Gitignore state collector failed", exc_info=True)
        gitignore = GitignoreSignal.NO_FILE

    try:
        gitattributes = collect_gitattributes_state(target)
    except Exception:
        logger.warning("Gitattributes state collector failed", exc_info=True)
        gitattributes = GitattributesSignal.NO_FILE

    try:
        mcp = collect_mcp_config_state(target)
    except Exception:
        logger.warning("MCP config state collector failed", exc_info=True)
        mcp = ConfigSignal.MISSING

    try:
        precommit = collect_precommit_state(target)
    except Exception:
        logger.warning("Precommit state collector failed", exc_info=True)
        precommit = PrecommitSignal.NO_FILE

    try:
        stale_mcp_seeds = collect_stale_seed_definitions(target)
    except Exception:
        logger.warning("Stale MCP seed collector failed", exc_info=True)
        stale_mcp_seeds = []

    try:
        vault_content, vault_annotation_count, vault_unreadable_count = (
            collect_vault_content_state(target)
        )
    except Exception:
        logger.warning("Vault content collector failed", exc_info=True)
        vault_content = VaultContentSignal.NO_VAULT
        vault_annotation_count = 0
        vault_unreadable_count = 0

    rename_integrity = RenameIntegritySignal.CLEAN
    rename_mismatch_count = 0
    if scope == "full":
        try:
            rename_integrity, rename_mismatch_count = collect_rename_integrity(target)
        except Exception:
            logger.warning("Rename integrity collector failed", exc_info=True)
            rename_integrity = RenameIntegritySignal.ERROR

    # Mode-mismatch compares the persisted declaration against the observed
    # hook and MCP artifact shapes. A failed probe is neutral (CLEAN), never a
    # crash, matching the other always-collected signals.
    try:
        mode_mismatch = collect_mode_mismatch_state(target)
    except Exception:
        logger.warning("Mode mismatch collector failed", exc_info=True)
        mode_mismatch = ModeMismatchSignal.CLEAN

    # Floor constraint is reported (not enforced) here: doctor surfaces a
    # below-floor workspace without raising, sharing the resolver's comparator.
    try:
        version_floor, version_floor_running, version_floor_minimum = (
            collect_version_floor_state(target)
        )
    except Exception:
        logger.warning("Version floor collector failed", exc_info=True)
        version_floor = VersionFloorSignal.OK
        version_floor_running = ""
        version_floor_minimum = ""

    # Per-package mode and floor: one diagnosis per distribution declared in the
    # shared workspace map, each read against its own entry. The top-level
    # mode_mismatch/version_floor above stay core's own view (the resolver reads
    # them); this map drives the doctor's per-package rows and covers companion
    # packages core's view cannot represent.
    package_diags: dict[str, PackageModeDiagnosis] = {}
    try:
        from ..workspace_mode import read_package_declarations

        declared_packages = read_package_declarations(target)
    except Exception:
        logger.warning("Package declarations read failed", exc_info=True)
        declared_packages = {}
    for pkg_name, pkg_decl in sorted(declared_packages.items()):
        try:
            pkg_mode_mismatch = collect_mode_mismatch_state(target, package=pkg_name)
        except Exception:
            logger.warning(
                "Mode mismatch collector failed for %s", pkg_name, exc_info=True
            )
            pkg_mode_mismatch = ModeMismatchSignal.CLEAN
        try:
            pkg_floor, pkg_floor_running, pkg_floor_minimum = (
                collect_version_floor_state(target, package=pkg_name)
            )
        except Exception:
            logger.warning(
                "Version floor collector failed for %s", pkg_name, exc_info=True
            )
            pkg_floor = VersionFloorSignal.OK
            pkg_floor_running = ""
            pkg_floor_minimum = ""
        package_diags[pkg_name] = PackageModeDiagnosis(
            package=pkg_name,
            declared_mode=pkg_decl.install_mode,
            mode_mismatch=pkg_mode_mismatch,
            version_floor=pkg_floor,
            version_floor_running=pkg_floor_running,
            version_floor_minimum=pkg_floor_minimum,
        )

    diag = WorkspaceDiagnosis(
        framework=framework,
        gitignore=gitignore,
        gitattributes=gitattributes,
        mcp=mcp,
        precommit=precommit,
        stale_mcp_seeds=stale_mcp_seeds,
        vault_content=vault_content,
        vault_annotation_count=vault_annotation_count,
        vault_unreadable_count=vault_unreadable_count,
        rename_integrity=rename_integrity,
        rename_mismatch_count=rename_mismatch_count,
        mode_mismatch=mode_mismatch,
        version_floor=version_floor,
        version_floor_running=version_floor_running,
        version_floor_minimum=version_floor_minimum,
        packages=package_diags,
    )

    if framework == FrameworkSignal.MISSING:
        return diag

    if framework in (FrameworkSignal.CORRUPTED, FrameworkSignal.ADOPTABLE):
        # Manifest may be broken or intentionally absent but directories may
        # still exist. Collect what we can without requiring a valid
        # WorkspaceContext.
        manifest_map: dict[str, ManifestEntrySignal] = {}
        try:
            manifest_map = collect_manifest_coherence(target)
        except Exception:
            logger.warning("Manifest coherence collector failed", exc_info=True)

        for tool in Tool:
            entry = manifest_map.get(tool.value, ManifestEntrySignal.NOT_INSTALLED)
            try:
                dir_state = collect_provider_dir_state(target, tool.value)
            except Exception:
                dir_state = ProviderDirSignal.MISSING
            diag.providers[tool] = ProviderDiagnosis(
                tool=tool,
                dir_state=dir_state,
                manifest_entry=entry,
            )

        # Adoption is the one path that claims a workspace vaultspec has never
        # written to locally, so it is the one path that must name what it would
        # overwrite before it writes anything. A corrupt manifest is a different
        # condition and keeps its existing repair semantics.
        if framework == FrameworkSignal.ADOPTABLE:
            try:
                diag.divergent_projections = collect_divergent_projections(target)
            except Exception:
                logger.warning("Divergent projection collector failed", exc_info=True)
        return diag

    # Layer 2: framework is PRESENT - collect manifest and builtin state
    manifest_map: dict[str, ManifestEntrySignal] = {}
    try:
        manifest_map = collect_manifest_coherence(target)
    except Exception:
        logger.warning("Manifest coherence collector failed", exc_info=True)

    try:
        diag.builtin_version = collect_builtin_version_state(target)
    except Exception:
        logger.warning("Builtin version collector failed", exc_info=True)

    try:
        from ...migrations import migration_status

        status, pending_names = migration_status(target)
        diag.migration_status = status.value
        diag.pending_migrations = list(pending_names)
    except Exception:
        logger.warning("Migration status collector failed", exc_info=True)

    if scope == "framework":
        # Build minimal provider entries from manifest data only
        for tool in Tool:
            entry = manifest_map.get(tool.value, ManifestEntrySignal.NOT_INSTALLED)
            diag.providers[tool] = ProviderDiagnosis(
                tool=tool,
                dir_state=ProviderDirSignal.MISSING,
                manifest_entry=entry,
            )
        return diag

    # Layer 3: scope is "full" or "sync" - collect per-provider details
    for tool in Tool:
        entry = manifest_map.get(tool.value, ManifestEntrySignal.NOT_INSTALLED)

        if entry == ManifestEntrySignal.NOT_INSTALLED:
            diag.providers[tool] = ProviderDiagnosis(
                tool=tool,
                dir_state=ProviderDirSignal.MISSING,
                manifest_entry=entry,
            )
            continue

        try:
            dir_state = collect_provider_dir_state(target, tool.value)
        except Exception:
            logger.warning(
                "Provider dir collector failed for %s", tool.value, exc_info=True
            )
            dir_state = ProviderDirSignal.MISSING

        try:
            config = collect_config_state(tool.value)
        except Exception:
            logger.warning(
                "Config state collector failed for %s", tool.value, exc_info=True
            )
            config = ConfigSignal.MISSING

        content: dict[str, ContentSignal] = {}
        if scope == "full":
            # Layer 4: full scope only - content integrity
            try:
                content = collect_content_integrity(tool.value)
            except Exception:
                logger.warning(
                    "Content integrity collector failed for %s",
                    tool.value,
                    exc_info=True,
                )

        diag.providers[tool] = ProviderDiagnosis(
            tool=tool,
            dir_state=dir_state,
            manifest_entry=entry,
            content=content,
            config=config,
        )

    return diag
