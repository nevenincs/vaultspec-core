"""Drive workspace initialization, install, and upgrade.

Composes the scaffolding, pre-commit, and mode-resolution primitives from
sibling modules into the full ``install``/``init``/``upgrade`` command
behaviors, including their dry-run previews.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

from . import types as _t
from .enums import InstallMode, ManagedState, Tool
from .exceptions import VaultSpecError, WorkspaceNotInitializedError
from .git_artifacts import (
    has_gitattributes_block,
    has_gitignore_block,
    untrack_managed_paths,
)
from .gitattributes import ensure_gitattributes_block
from .gitignore import (
    ensure_gitignore_block,
    get_recommended_entries,
    prune_orphaned_lock_sentinels,
)
from .install_mode import (
    fresh_install_schema_version,
    infer_upgrade_mode,
    persist_resolved_mode,
    stamp_manifest_version_no_downgrade,
    write_mode_declaration,
)
from .manifest import add_providers, read_manifest_data, write_manifest_data
from .precommit import scaffold_precommit
from .provider_registry import (
    PROVIDER_TO_TOOLS,
    filter_tools,
    rel,
    require_reconciliation_success,
    validate_provider,
    validate_skip,
)
from .provider_sync import sync_provider
from .scaffold import scaffold_core, scaffold_provider

logger = logging.getLogger(__name__)

__all__ = [
    "ensure_tool_configs",
    "init_run",
    "install_run",
]


def init_run(
    force: bool = False,
    provider: str = "all",
    skip: set[str] | None = None,
    mode: InstallMode | None = None,
    adopt: bool = False,
) -> list[tuple[str, str]]:
    """Scaffold the .vaultspec/ and .vault/ directory structure.

    Args:
        force: Override contents if already exists.
        provider: Provider to install.
        skip: Set of component names to skip (``core`` and/or provider names).
        mode: Resolved provisioning mode used to render the MCP definition and
            pre-commit hook entries. The fresh-install caller passes this
            explicitly because the committed workspace declaration is written
            only after scaffolding; ``None`` lets the renderers fall back to
            the declaration (dependency mode for a legacy workspace).
        adopt: Scaffold into an existing ``.vaultspec/`` instead of refusing.
            Adoption keeps ``force`` at its caller-supplied value, so seeding
            stays create-only and existing framework content is preserved.

    Returns:
        A deduplicated list of ``(relative_path, label)`` tuples for all
        created directories and files.
    """
    from vaultspec_core.config import get_config, reset_config
    from vaultspec_core.config.workspace import resolve_workspace
    from vaultspec_core.core.types import init_paths

    from .exceptions import ResourceExistsError

    skip = skip or set()
    skip_core = "core" in skip

    cfg = get_config()
    target = _t.get_context().target_dir
    fw_dir = target / cfg.framework_dir

    created: list[tuple[str, str]] = []

    if not skip_core:
        if fw_dir.exists() and not force and not adopt:
            raise ResourceExistsError(
                f"{fw_dir} already exists. Use --force to overwrite."
            )

        created = scaffold_core(target)

        # Seed builtin content directly into .vaultspec/
        from vaultspec_core.builtins import seed_builtins

        seeded = seed_builtins(fw_dir, force=force)
        for relative_path, _action in seeded:
            created.append((f".vaultspec/{relative_path}", "builtin"))

        # Snapshot builtins for revert support
        from .revert import snapshot_builtins

        snapshot_builtins(fw_dir)

    # Re-resolve workspace after scaffolding
    reset_config()
    layout = resolve_workspace(target_override=target)
    init_paths(layout)

    # Scaffold provider directories
    tools = filter_tools(PROVIDER_TO_TOOLS.get(provider, []), skip)
    for tool in tools:
        created.extend(scaffold_provider(target, tool))

    if "mcp" not in skip:
        from .mcps import mcp_sync, resolve_mcp_targets

        selected = tuple(tools)
        mcp_result = mcp_sync(
            mode=mode,
            target_dir=target,
            enrolled=selected,
        )
        require_reconciliation_success(
            mcp_result,
            operation="MCP provider-native enrollment",
        )
        for mcp_target in resolve_mcp_targets(
            target_dir=target,
            enrolled=selected,
        ):
            provider_result = mcp_result.per_tool.get(mcp_target.provider.value)
            if provider_result and provider_result.items:
                created.append((rel(target, mcp_target.path), "mcp"))
    if "precommit" not in skip:
        created.extend(scaffold_precommit(target, mode=mode))

    # Write provider manifest
    provider_names = [t.value for t in tools]
    if provider_names:
        add_providers(target, provider_names)

    # Deduplicate by relative path, preserving order
    seen: dict[str, str] = {}
    for relative_path, label in created:
        seen.setdefault(relative_path, label)

    return list(seen.items())


def ensure_tool_configs(path: Path) -> None:
    """Ensure TOOL_CONFIGS is populated, bootstrapping if needed.

    On a fresh project where ``.vaultspec/`` doesn't exist yet, uses a
    temporary directory as the workspace root so ``init_paths()`` can resolve
    the layout and populate TOOL_CONFIGS without touching the real filesystem.
    """
    import tempfile

    from vaultspec_core.config import reset_config
    from vaultspec_core.config.workspace import resolve_workspace
    from vaultspec_core.core.types import init_paths

    try:
        if _t.get_context().tool_configs:
            return
    except LookupError:
        pass

    fw_dir = path / ".vaultspec"
    if fw_dir.exists():
        reset_config()
        layout = resolve_workspace(target_override=path)
        init_paths(layout)
        return

    # Bootstrap in a temporary directory to avoid TOCTOU on the real path.
    # Resolve workspace against the temp dir, then re-initialize with the
    # real target so tool_config paths reference the actual workspace.
    # Resolved because this temp directory is immediately used AS a workspace
    # target, and scaffolding derives provider paths with `Path.relative_to`.
    # On Windows `tempfile` can hand back an 8.3 short path whose children
    # enumerate in expanded form, which makes that lexical comparison raise.
    tmp = Path(tempfile.mkdtemp()).resolve()
    try:
        tmp_fw = tmp / ".vaultspec"
        tmp_fw.mkdir(parents=True, exist_ok=True)

        reset_config()
        layout = resolve_workspace(target_override=tmp)
        # Replace the temp target with the real path so tool_configs point correctly
        from vaultspec_core.config.workspace import WorkspaceLayout

        real_layout = WorkspaceLayout(
            target_dir=path,
            vault_dir=path / ".vault",
            vaultspec_dir=path / ".vaultspec",
            mode=layout.mode,
            git=layout.git,
        )
        init_paths(real_layout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _preview_upgrade_items(
    path: Path, provider: str, skip: set[str], *, skip_core: bool
) -> list[tuple[str, str]]:
    """Enumerate what ``install --upgrade --dry-run`` would change.

    The real upgrade re-seeds builtins AND runs the provider sync, which
    backfills new provider files and structural directories. Preview that
    provider-side work too so the dry-run enumerates what the real run
    changes rather than only the builtin seed (issue #134). Only the
    changed entries are surfaced to keep the preview signal-dense; an
    unchanged provider tree contributes nothing.

    Raises:
        VaultSpecError: If the provider reconciliation preview fails.
    """
    ensure_tool_configs(path)
    items: list[tuple[str, str]] = []
    if not skip_core:
        from vaultspec_core.builtins import seed_builtins

        items = seed_builtins(path / ".vaultspec", force=True, dry_run=True)

    if not path.joinpath(".vaultspec").exists():
        return items

    sync_target = provider if provider not in ("all", "core") else "all"
    try:
        sync_results = sync_provider(sync_target, dry_run=True, skip=skip)
    except OSError as exc:
        raise VaultSpecError(
            "Provider reconciliation preview failed.", hint=str(exc)
        ) from exc
    require_reconciliation_success(
        sync_results,
        operation="Provider reconciliation preview",
    )
    seen_preview = {rel for rel, _ in items}
    for sync_result in sync_results:
        for relative_path, action in sync_result.items:
            if action in ("[UNCHANGED]", "[SKIP]"):
                continue
            if relative_path in seen_preview:
                continue
            seen_preview.add(relative_path)
            items.append((relative_path, action))
    return items


def _preview_install_manifest(
    path: Path,
    provider: str,
    skip: set[str],
    *,
    skip_core: bool,
    resolved_mode: InstallMode,
) -> list[tuple[str, str]]:
    """Enumerate the files a fresh ``install --dry-run`` would create.

    Raises:
        VaultSpecError: If the MCP enrollment preview fails.
    """
    ensure_tool_configs(path)

    manifest: list[tuple[str, str]] = []
    if not skip_core:
        manifest = scaffold_core(path, dry_run=True)

        # Include builtin files that would be seeded
        from vaultspec_core.builtins import list_builtins

        for builtin_rel in list_builtins():
            manifest.append((f".vaultspec/{builtin_rel}", "builtin"))

    tools = filter_tools(PROVIDER_TO_TOOLS.get(provider, []), skip)
    for tool in tools:
        manifest.extend(scaffold_provider(path, tool, dry_run=True))
    if "mcp" not in skip:
        manifest.extend(
            _preview_mcp_targets(
                path, tuple(tools), skip_core=skip_core, resolved_mode=resolved_mode
            )
        )
    if "precommit" not in skip:
        manifest.extend(scaffold_precommit(path, dry_run=True, mode=resolved_mode))

    # Deduplicate preserving order (by relative path)
    seen: dict[str, str] = {}
    for relative_path, label in manifest:
        seen.setdefault(relative_path, label)
    return list(seen.items())


def _preview_mcp_targets(
    path: Path,
    selected: tuple[Tool, ...],
    *,
    skip_core: bool,
    resolved_mode: InstallMode,
) -> list[tuple[str, str]]:
    """Enumerate the native MCP targets a fresh install would enroll.

    Raises:
        VaultSpecError: If the MCP enrollment preview fails.
    """
    from .mcps import mcp_sync, resolve_mcp_targets

    mcp_result = mcp_sync(
        dry_run=True,
        mode=resolved_mode,
        target_dir=path,
        enrolled=selected,
    )
    require_reconciliation_success(
        mcp_result,
        operation="MCP provider-native enrollment preview",
    )
    entries: list[tuple[str, str]] = []
    for mcp_target in resolve_mcp_targets(target_dir=path, enrolled=selected):
        provider_result = mcp_result.per_tool.get(mcp_target.provider.value)
        if not skip_core or (provider_result and provider_result.items):
            entries.append((rel(path, mcp_target.path), "mcp"))
    return entries


def _detect_precommit_managed(path: Path) -> bool:
    """Report whether *path* still carries vaultspec-managed pre-commit hooks."""
    from .diagnosis.collectors import collect_precommit_state
    from .diagnosis.signals import PrecommitSignal

    return collect_precommit_state(path) not in (
        PrecommitSignal.NO_FILE,
        PrecommitSignal.NO_HOOKS,
    )


def _reseed_builtins(path: Path) -> list[tuple[str, str]]:
    """Re-seed the builtin corpus and re-snapshot it for revert support."""
    from vaultspec_core.builtins import seed_builtins

    from .revert import snapshot_builtins

    fw_dir = path / ".vaultspec"
    seeded = seed_builtins(fw_dir, force=True)
    snapshot_builtins(fw_dir)
    return seeded


def _migrate_mcp_launch_shape(path: Path, resolved_mode: InstallMode) -> None:
    """Force every declared package's managed MCP entry into *resolved_mode*.

    Closes the mode-flip force-gate asymmetry: when the mode flipped, the
    force-gated MCP pass skipped every stale managed entry declared in the
    workspace, not just core's own. Forcing them here migrates all three
    renderers atomically in this run; user-owned entries and the foreign-entry
    discipline remain untouched.

    Raises:
        VaultSpecError: If the reconciliation reports a failure.
    """
    from .mcps import mcp_sync
    from .workspace_mode import read_package_declarations

    declared_packages = frozenset(read_package_declarations(path))
    mcp_result = mcp_sync(
        mode=resolved_mode,
        force_managed=declared_packages or frozenset({"vaultspec-core"}),
    )
    require_reconciliation_success(
        mcp_result,
        operation="MCP mode-migration reconciliation",
    )


def _finalize_upgrade_manifest(
    path: Path, *, force: bool, resolved_mode: InstallMode
) -> None:
    """Stamp manifest state and reconcile the git index after an upgrade."""
    import datetime

    mdata = read_manifest_data(path)
    if not mdata.installed_at:
        mdata.installed_at = datetime.datetime.now(tz=datetime.UTC).isoformat()
    stamp_manifest_version_no_downgrade(mdata)

    for orphan in prune_orphaned_lock_sentinels(path):
        logger.info("Removed orphaned lock sentinel %s", orphan)

    # Re-opt-in gitignore management on --upgrade --force
    if force:
        ensure_gitignore_block(
            path,
            get_recommended_entries(path),
            state=ManagedState.PRESENT,
        )
        mdata.gitignore_managed = True

    mdata.precommit_managed = _detect_precommit_managed(path)

    persist_resolved_mode(path, mdata, resolved_mode)
    write_manifest_data(path, mdata)

    # Reconcile git index with the managed gitignore block so that
    # historically-committed state files (e.g. .vaultspec/providers.json
    # from a pre-managed-block install) stop showing up as dirty on
    # every subsequent run.
    untrack_managed_paths(path, get_recommended_entries(path))


def _run_upgrade(
    path: Path,
    provider: str,
    skip: set[str],
    *,
    skip_core: bool,
    mode: InstallMode | None,
    force: bool,
) -> dict[str, Any]:
    """Re-seed builtins, migrate schema, and reconcile providers in place.

    Raises:
        WorkspaceNotInitializedError: If *path* is not an initialized workspace.
        VaultSpecError: If provider or MCP reconciliation reports a failure.
    """
    from vaultspec_core.config.workspace import WorkspaceError, resolve_workspace
    from vaultspec_core.core.types import init_paths

    from .workspace_mode import dependency_leak_advisory, newly_establishes_dependency

    try:
        layout = resolve_workspace(target_override=path)
        init_paths(layout)
    except WorkspaceError as e:
        raise WorkspaceNotInitializedError(
            f"Cannot upgrade: {e}",
            hint=f"Run 'vaultspec-core install {path}' first.",
        ) from e

    # Q6 migration: refine the provision-time resolution with this
    # workspace's deployed state. A legacy workspace carries no persisted
    # mode, so infer it from the observed hook shape and the pyproject
    # dependency listing; a workspace that already declares a mode keeps it,
    # which is what makes a repeated upgrade idempotent. This supersedes the
    # value resolve_install_mode computed at entry, since only here is the
    # deployed hook shape folded in - so the leak advisory is recomputed from
    # the inferred provenance too: a persisted dependency declaration stays
    # silent, a freshly inferred one warns.
    inferred = infer_upgrade_mode(path, mode)
    resolved_mode = inferred.mode
    leak_warnings = (
        [dependency_leak_advisory()] if newly_establishes_dependency(inferred) else []
    )

    seeded: list[tuple[str, str]] = [] if skip_core else _reseed_builtins(path)

    # Run pending schema migrations BEFORE the sync. ``sync_provider``
    # ends with ``mdata.vaultspec_version = package_version()``, which
    # would otherwise mask any migration whose ``target_version``
    # equals the running release: ``run_pending_migrations`` would
    # read the just-bumped version and find nothing pending. Running
    # the driver first preserves the pre-upgrade manifest version so
    # the registry sees the real "needs migration" state, applies
    # the pending entries, and then ``sync_provider`` re-bumps to
    # the running version on its way out.
    from ..migrations import run_pending_migrations

    run_pending_migrations(path)

    # Persist the inferred declaration BEFORE the provider sync and the hook
    # scaffold re-render their artifacts. Both renderers resolve their mode
    # from the committed declaration (via resolve_render_mode); on a legacy
    # workspace with no declaration that fallback renders dependency mode, so
    # an inference that landed tool mode would otherwise leave uv-run-shaped
    # artifacts contradicting the tool-mode declaration written moments
    # later. Writing it here threads the inferred mode into this same run's
    # rendering, mirroring the fresh-install ordering. The manifest echo and
    # floor reconciliation still run once, later, via persist_resolved_mode.
    write_mode_declaration(path, resolved_mode)

    # Detect a mode flip before the sync below re-renders any artifact.
    # The pre-commit and declaration renderers rewrite unconditionally, but
    # the MCP sync runs force-gated: a pre-existing MANAGED vaultspec-core
    # entry still carrying the old mode's launch shape is skipped unless
    # --force, which would leave the migration non-atomic across the three
    # renderers until a later forced re-sync (mode-flip-force-asymmetry
    # audit finding). Captured here against the still-old .mcp.json, this
    # flags whether the deployed MCP launch shape disagrees with the mode
    # this upgrade resolved to; the targeted force below closes the gap.
    from .diagnosis.collectors import observed_mcp_mode

    observed_mode = observed_mcp_mode(path)
    mcp_mode_flipped = observed_mode is not None and observed_mode != resolved_mode

    sync_target = provider if provider not in ("all", "core") else "all"
    # `sync_provider` rejects `core` in its skip set (`allow_core=False`).
    # `install_run` accepts `core` because it skips the framework scaffold;
    # filter it out before forwarding to the sync pass.
    # Forward `force`: `--upgrade` and `--force` are separate flags;
    # `install --upgrade` (without `--force`) must preserve user-authored
    # content. The pre-collapse hardcoded `force=True` was an asymmetry
    # against the fresh-install path and silently overwrote user content
    # on every upgrade. See PR #116 review thread r3260188496.
    sync_results = sync_provider(sync_target, force=force, skip=skip - {"core"})
    require_reconciliation_success(
        sync_results,
        operation="Provider reconciliation during upgrade",
    )

    if "precommit" not in skip:
        scaffold_precommit(path, mode=resolved_mode)

    # Skipped when --force already rewrote it, when the mode did not flip
    # (preserving today's force-gated semantics for a same-mode divergent entry,
    # now handled by the fingerprint-verified refresh path in the sync above), or
    # when mcp sync is skipped outright.
    if mcp_mode_flipped and not force and "mcp" not in skip:
        _migrate_mcp_launch_shape(path, resolved_mode)

    _finalize_upgrade_manifest(path, force=force, resolved_mode=resolved_mode)

    return {
        "action": "upgrade",
        "items": seeded,
        "path": path,
        "warnings": leak_warnings,
    }


def install_run(
    path: Path,
    provider: str = "all",
    upgrade: bool = False,
    dry_run: bool = False,
    force: bool = False,
    skip: set[str] | None = None,
    mode: InstallMode | None = None,
    adopt: bool = False,
) -> dict[str, Any]:
    """Deploy the vaultspec framework to a project directory.

    Args:
        path: Target directory.
        provider: Provider to install (``all``, ``core``, ``claude``, etc.).
        upgrade: Re-sync builtin rules without re-scaffolding.
        dry_run: Preview the manifest of files that would be created.
        force: Override contents if installation already exists.
        skip: Set of component names to skip (``core`` and/or provider names).
        mode: Explicit provisioning mode from the ``--mode`` flag, or ``None``
            to let the workspace fall back to the default. The resolved mode is
            persisted once at provision time to the committed workspace
            declaration and echoed into the manifest.
        adopt: Treat an existing but unmanifested ``.vaultspec/`` as adoptable
            rather than as an already-installed workspace, so the install
            proceeds additively instead of demanding ``--force``. The CLI passes
            the framework signal it observed before pre-flight ran; when
            ``False`` the state is re-detected here.

    Returns:
        A dict describing the result:
        - ``"action"``: ``"dry_run"``, ``"upgrade"``, or ``"install"``
        - ``"items"``: list of ``(path, label)`` tuples (for dry_run);
          list of ``(builtin_path, action)`` tuples (for upgrade)

    Raises:
        ProviderError: If *provider* is invalid.
        ResourceExistsError: If already installed and *force*/*upgrade* not set.
    """
    from vaultspec_core.config import reset_config
    from vaultspec_core.config.workspace import resolve_workspace
    from vaultspec_core.core.types import init_paths

    from .exceptions import ResourceExistsError

    validate_provider(provider)
    skip = validate_skip(skip)

    # Bootstrap a minimal context so downstream code can read target_dir
    _t.set_context(
        _t.WorkspaceContext(
            root_dir=path,
            target_dir=path,
            rules_src_dir=path,
            skills_src_dir=path,
            agents_src_dir=path,
            system_src_dir=path,
            templates_dir=path,
            hooks_dir=path,
        )
    )

    skip_core = "core" in skip

    # Adoption: a workspace that tracks canonical framework content but carries
    # no runtime manifest (gitignored and per-machine by design) is claimed by an
    # ordinary run, never by --force. The caller passes the observation it made
    # before pre-flight established the manifest; a direct API caller that ran no
    # pre-flight is served by the self-detection below. Both routes land on the
    # same additive install: seeding and scaffolding stay create-only, so nothing
    # already on disk is overwritten.
    from .diagnosis.collectors import collect_framework_presence
    from .diagnosis.signals import FrameworkSignal

    adopting = adopt or (collect_framework_presence(path) is FrameworkSignal.ADOPTABLE)

    if skip_core and not (path / ".vaultspec").exists():
        raise VaultSpecError(
            f"Cannot skip core: .vaultspec/ does not exist at {path}.",
            hint="Install core first, then use --skip core on subsequent installs.",
        )

    # Resolve the provisioning mode once, at provision time, via the Q5
    # precedence chain (explicit flag, persisted declaration, pyproject
    # detection, default tool mode). An explicit request that names an
    # impossible combination - dependency mode with no pyproject.toml - raises a
    # loud, typed refusal here rather than silently falling back. The provenance
    # rides along so the dependency-leak advisory fires only when this run is the
    # one electing dependency mode, not on a persisted read.
    from .workspace_mode import (
        dependency_leak_advisory,
        newly_establishes_dependency,
        resolve_install_mode_with_provenance,
    )

    resolved = resolve_install_mode_with_provenance(path, explicit=mode)
    resolved_mode = resolved.mode
    leak_warnings = (
        [dependency_leak_advisory()] if newly_establishes_dependency(resolved) else []
    )

    if upgrade and dry_run:
        return {
            "action": "upgrade",
            "items": _preview_upgrade_items(path, provider, skip, skip_core=skip_core),
            "path": path,
            "dry_run": True,
            "warnings": leak_warnings,
        }

    if dry_run:
        return {
            "action": "dry_run",
            "items": _preview_install_manifest(
                path,
                provider,
                skip,
                skip_core=skip_core,
                resolved_mode=resolved_mode,
            ),
            "path": path,
            "warnings": leak_warnings,
        }

    if upgrade:
        return _run_upgrade(
            path,
            provider,
            skip,
            skip_core=skip_core,
            mode=mode,
            force=force,
        )

    fw_dir = path / ".vaultspec"
    if fw_dir.exists() and not force and not skip_core and not adopting:
        raise ResourceExistsError(
            f"vaultspec is already installed at {path}. "
            "Use --upgrade to update, --force to override, or remove it "
            f"first with 'vaultspec-core uninstall {path}'."
        )

    created = init_run(
        force=force,
        provider=provider,
        skip=skip,
        mode=resolved_mode,
        adopt=adopting,
    )

    reset_config()
    layout = resolve_workspace(target_override=path)
    init_paths(layout)

    # Persist the committed declaration before the provider sync below re-renders
    # the MCP config and pre-commit hooks. Those renderers resolve their mode
    # from the declaration; writing it here means the just-resolved mode governs
    # the sync pass instead of the legacy-absent dependency bridge, which would
    # otherwise clobber the tool-mode artifacts init_run just wrote. The manifest
    # echo and floor reconciliation still happen once, later, via
    # persist_resolved_mode after the manifest is read.
    write_mode_declaration(path, resolved_mode)

    post_errors: list[str] = []

    sync_target = provider if provider not in ("all", "core") else "all"
    try:
        # Filter `core` out: `sync_provider` rejects it, but `install_run`
        # accepts it as a "framework only, skip provider sync" hint.
        # Forward `force`: `install --force` must propagate to the sync
        # pass so user-authored system prompts and provider configs are
        # overwritten consistently with the rest of the install.
        sync_provider(sync_target, force=force, skip=skip - {"core"})
    except (VaultSpecError, OSError) as exc:
        logger.warning("Sync failed during install: %s", exc)
        post_errors.append(f"sync: {exc}")

    # Count actual source resources (what the user authored)
    from .agents import collect_agents
    from .mcps import collect_mcp_servers
    from .rules import collect_rules
    from .skills import collect_skills

    source_counts = {
        "rules": len(collect_rules()),
        "skills": len(collect_skills()),
        "agents": len(collect_agents()),
        "mcps": len(collect_mcp_servers()),
    }

    tools = filter_tools(PROVIDER_TO_TOOLS.get(provider, []), skip)
    provider_names = [t.value for t in tools]
    from .mcps import resolve_mcp_targets

    has_mcp = any(
        target.path.exists()
        for target in resolve_mcp_targets(target_dir=path, enrolled=tuple(tools))
    )

    # Retire sentinels whose subject is gone (e.g. .pre-commit-config.yaml.lock
    # after a checkout migrates to prek.toml) before the ignore entries are
    # computed: managed_lock_paths only covers sentinels with a live subject, so
    # an orphan left in place would stay permanently visible in git status.
    for orphan in prune_orphaned_lock_sentinels(path):
        logger.info("Removed orphaned lock sentinel %s", orphan)

    # Manage gitignore block
    recommended = get_recommended_entries(path)

    gi_written = ensure_gitignore_block(path, recommended, state=ManagedState.PRESENT)
    if gi_written:
        logger.info("Added vaultspec managed block to .gitignore")

    # Manage gitattributes block
    ga_written = ensure_gitattributes_block(path, state=ManagedState.PRESENT)
    if ga_written:
        logger.info("Added vaultspec managed block to .gitattributes")

    # Populate v2.0 manifest fields
    import datetime

    mdata = read_manifest_data(path, strict=True)

    # Robust detection: if it's there, it's managed.
    mdata.gitignore_managed = has_gitignore_block(path / ".gitignore")
    mdata.gitattributes_managed = has_gitattributes_block(path / ".gitattributes")
    mdata.precommit_managed = _detect_precommit_managed(path)

    mdata.vaultspec_version = fresh_install_schema_version()
    mdata.installed_at = datetime.datetime.now(tz=datetime.UTC).isoformat()
    for name in provider_names:
        mdata.provider_state.setdefault(name, {})
        mdata.provider_state[name]["installed_at"] = mdata.installed_at
    persist_resolved_mode(path, mdata, resolved_mode)
    write_manifest_data(path, mdata)

    # Reconcile git index with the managed gitignore block so that
    # historically-committed state files (e.g. .vaultspec/providers.json
    # from a pre-managed-block install) stop showing up as dirty on
    # every subsequent run.
    untrack_managed_paths(path, recommended)

    result: dict[str, Any] = {
        "action": "install",
        "items": created,
        "source_counts": source_counts,
        "providers": provider_names,
        "has_mcp": has_mcp,
        "path": path,
        "warnings": leak_warnings,
    }
    if post_errors:
        result["errors"] = post_errors
    return result
