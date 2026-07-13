"""Dataclasses aggregating diagnostic signals for providers and workspaces.

The :func:`diagnose` orchestrator drives layered signal collection, delegating
to the individual collectors in :mod:`.collectors`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from ..enums import Tool
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
)

logger = logging.getLogger(__name__)


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
        mode_mismatch: Coherence between the persisted install-mode declaration
            and the shape of the provisioned hook and MCP artifacts.
    """

    framework: FrameworkSignal
    providers: dict[Tool, ProviderDiagnosis] = field(default_factory=dict)
    builtin_version: BuiltinVersionSignal = BuiltinVersionSignal.NO_SNAPSHOTS
    gitignore: GitignoreSignal = GitignoreSignal.NO_FILE
    gitattributes: GitattributesSignal = GitattributesSignal.NO_FILE
    mcp: ConfigSignal = ConfigSignal.MISSING
    precommit: PrecommitSignal = PrecommitSignal.NO_FILE
    migration_status: str = "up_to_date"
    pending_migrations: list[str] = field(default_factory=list)
    vault_content: VaultContentSignal = VaultContentSignal.NO_VAULT
    vault_annotation_count: int = 0
    vault_unreadable_count: int = 0
    rename_integrity: RenameIntegritySignal = RenameIntegritySignal.CLEAN
    rename_mismatch_count: int = 0
    mode_mismatch: ModeMismatchSignal = ModeMismatchSignal.CLEAN


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
        collect_framework_presence,
        collect_gitattributes_state,
        collect_gitignore_state,
        collect_manifest_coherence,
        collect_mcp_config_state,
        collect_mode_mismatch_state,
        collect_precommit_state,
        collect_provider_dir_state,
        collect_rename_integrity,
        collect_vault_content_state,
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

    diag = WorkspaceDiagnosis(
        framework=framework,
        gitignore=gitignore,
        gitattributes=gitattributes,
        mcp=mcp,
        precommit=precommit,
        vault_content=vault_content,
        vault_annotation_count=vault_annotation_count,
        vault_unreadable_count=vault_unreadable_count,
        rename_integrity=rename_integrity,
        rename_mismatch_count=rename_mismatch_count,
        mode_mismatch=mode_mismatch,
    )

    if framework == FrameworkSignal.MISSING:
        return diag

    if framework == FrameworkSignal.CORRUPTED:
        # Manifest may be broken but directories may still exist.
        # Collect what we can without requiring a valid WorkspaceContext.
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
