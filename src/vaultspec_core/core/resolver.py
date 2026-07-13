"""Resolution engine that maps diagnosed workspace state to corrective actions.

Takes a :class:`~vaultspec_core.core.diagnosis.WorkspaceDiagnosis` and a
requested CLI action, then produces a :class:`ResolutionPlan` of ordered steps,
warnings, and blocking conflicts. Follows the rule matrix defined in the
cli-ambiguous-states ADR.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from .diagnosis.signals import (
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
    ResolutionAction,
)
from .enums import CliAction
from .helpers import parse_version_tuple

logger = logging.getLogger(__name__)


@dataclass
class ResolutionStep:
    """A single corrective action within a :class:`ResolutionPlan`.

    Args:
        action: The :class:`~vaultspec_core.core.diagnosis.signals.ResolutionAction`
            to perform.
        target: What the action operates on (provider name, file path, etc.).
        reason: Human-readable explanation of why this step is needed.
    """

    action: ResolutionAction
    target: str
    reason: str


@dataclass
class ResolutionPlan:
    """Accumulated plan of resolution steps, warnings, and conflicts.

    Args:
        steps: Ordered list of :class:`ResolutionStep` to execute.
        warnings: Non-blocking advisories emitted before execution.
        conflicts: Blocking issues that prevent execution.
    """

    steps: list[ResolutionStep] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        """Return ``True`` if the plan has unresolved conflicts."""
        return len(self.conflicts) > 0


def resolve(
    diagnosis: WorkspaceDiagnosis,
    action: CliAction | str,
    provider: str = "all",
    *,
    force: bool = False,
    dry_run: bool = False,
    target: Path | None = None,
) -> ResolutionPlan:
    """Build a resolution plan from diagnosed workspace state.

    Evaluates the full rule matrix against the diagnosis signals and
    requested action. Framework-level rules are checked first, then
    per-provider rules, then cross-cutting concerns (builtins, gitignore).

    Args:
        diagnosis: Populated :class:`WorkspaceDiagnosis` from
            :func:`~vaultspec_core.core.diagnosis.diagnose`.
        action: CLI action being performed - one of ``"install"``,
            ``"sync"``, ``"uninstall"``.
        provider: Provider scope - ``"all"`` or a specific provider name.
        force: When ``True``, escalates warnings to corrective steps.
        dry_run: When ``True``, the plan is informational only.
        target: Workspace root directory. Used to read manifest flags.
            Falls back to :func:`~vaultspec_core.core.types.get_context`
            if not provided.

    Returns:
        A :class:`ResolutionPlan` with steps, warnings, and conflicts.
    """
    _ = dry_run  # reserved for executor phase
    action = CliAction(action)
    plan = ResolutionPlan()

    if action == CliAction.DOCTOR:
        return plan

    # Upgrade = install semantics for framework, sync for providers.
    fw_action = CliAction.INSTALL if action == CliAction.UPGRADE else action
    prov_action = CliAction.SYNC if action == CliAction.UPGRADE else action

    _resolve_framework(plan, diagnosis.framework, fw_action, force=force)
    _resolve_version_warning(plan, diagnosis)
    # Builtins live directly under .vaultspec/ - framework content. Under
    # `install --upgrade` they are re-seeded unconditionally, so the
    # builtin-version signal must resolve with framework semantics; using
    # prov_action (SYNC) would wrongly tell the operator to pass --force
    # to re-seed something the upgrade is already about to re-seed.
    _resolve_builtin_version(plan, diagnosis.builtin_version, fw_action, force=force)
    _resolve_gitignore(plan, diagnosis.gitignore, prov_action, force=force)
    _resolve_gitattributes(plan, diagnosis.gitattributes, prov_action, force=force)

    # Determine precommit management state from manifest
    pc_managed = True
    if target is None:
        try:
            from .types import get_context

            target = get_context().target_dir
        except LookupError:
            pass
    if target is not None:
        try:
            from .manifest import read_manifest_data

            _mdata = read_manifest_data(target)
            pc_managed = _mdata.precommit_managed
        except Exception:
            pc_managed = True

    # The canonical entry prefix the non-canonical precommit advisory names is
    # mode-dependent: a tool-mode workspace should be told to use the uvx form,
    # not the dependency-mode uv-run form. Resolve it from the persisted mode,
    # falling back to the dependency-mode prefix if the mode cannot be read.
    expected_entry_prefix = "uv run --no-sync vaultspec-core"
    if target is not None:
        try:
            from .commands import entry_prefix_for_mode
            from .workspace_mode import resolve_render_mode

            expected_entry_prefix = entry_prefix_for_mode(resolve_render_mode(target))
        except Exception:
            logger.debug(
                "Could not resolve render mode for precommit advisory", exc_info=True
            )

    _resolve_precommit(
        plan,
        diagnosis.precommit,
        prov_action,
        force=force,
        precommit_managed=pc_managed,
        expected_entry_prefix=expected_entry_prefix,
    )
    _resolve_mode_mismatch(plan, diagnosis.mode_mismatch)

    # Per-provider rules
    for tool, prov_diag in diagnosis.providers.items():
        if provider != "all" and tool.value != provider:
            continue
        name = tool.value
        _resolve_manifest_entry(
            plan,
            prov_diag.manifest_entry,
            name,
            prov_action,
            force=force,
        )
        _resolve_provider_dir(
            plan,
            prov_diag.dir_state,
            name,
            prov_action,
            force=force,
        )
        _resolve_content(
            plan,
            prov_diag.content,
            name,
            prov_action,
            force=force,
        )
        _resolve_config(
            plan,
            prov_diag.config,
            name,
            prov_action,
            force=force,
        )

    return plan


# ---------------------------------------------------------------------------
# Framework rules
# ---------------------------------------------------------------------------


def _resolve_framework(
    plan: ResolutionPlan,
    signal: FrameworkSignal,
    action: CliAction,
    *,
    force: bool,
) -> None:
    """Apply framework-level resolution rules."""
    if signal == FrameworkSignal.PRESENT:
        return

    if signal == FrameworkSignal.MISSING:
        if action == CliAction.INSTALL:
            # Proceed normally - install will scaffold
            return
        if action == CliAction.SYNC:
            plan.conflicts.append(
                "Framework not installed. Run 'vaultspec-core install' first."
            )
            return
        if action == CliAction.UNINSTALL:
            plan.warnings.append("Nothing to remove - framework is not installed.")
            return

    if signal == FrameworkSignal.CORRUPTED:
        if action == CliAction.INSTALL:
            if force:
                plan.steps.append(
                    ResolutionStep(
                        action=ResolutionAction.REPAIR_MANIFEST,
                        target="manifest",
                        reason="Manifest corrupted, repairing before install",
                    )
                )
            else:
                plan.conflicts.append("Manifest is corrupted. Use --force to repair.")
            return
        if action == CliAction.SYNC:
            plan.steps.append(
                ResolutionStep(
                    action=ResolutionAction.REPAIR_MANIFEST,
                    target="manifest",
                    reason="Manifest corrupted, repairing before sync",
                )
            )
            plan.steps.append(
                ResolutionStep(
                    action=ResolutionAction.SYNC,
                    target="all",
                    reason="Sync after manifest repair",
                )
            )
            return
        if action == CliAction.UNINSTALL:
            if force:
                plan.steps.append(
                    ResolutionStep(
                        action=ResolutionAction.REPAIR_MANIFEST,
                        target="manifest",
                        reason="Corrupted manifest - repairing before uninstall",
                    )
                )
            else:
                plan.conflicts.append(
                    "Manifest is corrupted. Use --force to proceed with uninstall."
                )
            return

    # All FrameworkSignal values are handled above; this is unreachable
    # unless a new enum member is added without updating the resolver.
    logger.warning("Unknown FrameworkSignal member: %s (action=%s)", signal, action)


# ---------------------------------------------------------------------------
# Manifest entry rules
# ---------------------------------------------------------------------------


def _resolve_manifest_entry(
    plan: ResolutionPlan,
    signal: ManifestEntrySignal,
    tool_name: str,
    action: CliAction,
    *,
    force: bool,
) -> None:
    """Apply manifest-entry resolution rules for a single provider."""
    if signal in (ManifestEntrySignal.COHERENT, ManifestEntrySignal.NOT_INSTALLED):
        return

    if signal == ManifestEntrySignal.ORPHANED and action in (
        CliAction.INSTALL,
        CliAction.SYNC,
    ):
        plan.steps.append(
            ResolutionStep(
                action=ResolutionAction.SCAFFOLD,
                target=tool_name,
                reason=f"Provider '{tool_name}' in manifest but directory missing",
            )
        )
        if action == CliAction.SYNC:
            plan.steps.append(
                ResolutionStep(
                    action=ResolutionAction.SYNC,
                    target=tool_name,
                    reason=f"Sync after scaffolding '{tool_name}'",
                )
            )
        return

    if signal == ManifestEntrySignal.UNTRACKED:
        if action == CliAction.INSTALL:
            plan.steps.append(
                ResolutionStep(
                    action=ResolutionAction.ADOPT_DIRECTORY,
                    target=tool_name,
                    reason=f"Directory for '{tool_name}' exists but is not in manifest",
                )
            )
            return
        if action == CliAction.SYNC:
            if force:
                plan.steps.append(
                    ResolutionStep(
                        action=ResolutionAction.ADOPT_DIRECTORY,
                        target=tool_name,
                        reason=f"Adopting untracked directory for '{tool_name}'",
                    )
                )
                plan.steps.append(
                    ResolutionStep(
                        action=ResolutionAction.SYNC,
                        target=tool_name,
                        reason=f"Sync after adopting '{tool_name}'",
                    )
                )
            else:
                plan.warnings.append(
                    f"Provider '{tool_name}' has an untracked directory. "
                    f"Use --force to adopt and sync."
                )
            return
        if action == CliAction.UNINSTALL:
            if force:
                plan.steps.append(
                    ResolutionStep(
                        action=ResolutionAction.REMOVE,
                        target=tool_name,
                        reason=f"Removing untracked directory for '{tool_name}'",
                    )
                )
            else:
                plan.conflicts.append(
                    f"Provider '{tool_name}' has an untracked directory. "
                    f"Use --force to remove."
                )
            return

    if signal == ManifestEntrySignal.ORPHANED and action == CliAction.UNINSTALL:
        # Orphaned on uninstall: directory already missing, manifest entry
        # will be cleaned up by the uninstall command itself.
        return

    # All ManifestEntrySignal values are handled above.
    logger.warning("Unknown ManifestEntrySignal member: %s (action=%s)", signal, action)


# ---------------------------------------------------------------------------
# Provider directory rules
# ---------------------------------------------------------------------------


def _resolve_provider_dir(
    plan: ResolutionPlan,
    signal: ProviderDirSignal,
    tool_name: str,
    action: CliAction,
    *,
    force: bool,
) -> None:
    """Apply provider-directory resolution rules for a single provider."""
    if signal in (ProviderDirSignal.COMPLETE, ProviderDirSignal.MISSING):
        return

    if signal == ProviderDirSignal.MIXED and action == CliAction.UNINSTALL:
        if force:
            plan.steps.append(
                ResolutionStep(
                    action=ResolutionAction.REMOVE,
                    target=tool_name,
                    reason=f"Force-removing '{tool_name}' directory with mixed content",
                )
            )
        else:
            plan.conflicts.append(
                f"Provider '{tool_name}' directory contains files not managed "
                f"by vaultspec (user-created content outside rules/, skills/, "
                f"agents/ subdirectories). Use --force to remove."
            )
        return

    if signal == ProviderDirSignal.MIXED and action in (
        CliAction.INSTALL,
        CliAction.SYNC,
    ):
        # Mixed content during install/sync: the command will sync managed
        # resources without touching unrecognized files.
        return

    is_syncable = signal in (ProviderDirSignal.EMPTY, ProviderDirSignal.PARTIAL)
    if is_syncable and action == CliAction.SYNC:
        plan.steps.append(
            ResolutionStep(
                action=ResolutionAction.SYNC,
                target=tool_name,
                reason=f"Provider '{tool_name}' directory is {signal.value}",
            )
        )
        return

    if is_syncable and action == CliAction.INSTALL:
        # Empty/partial during install: install will scaffold and sync.
        return

    if is_syncable and action == CliAction.UNINSTALL:
        # Empty/partial during uninstall: the directory will be removed.
        return

    if signal == ProviderDirSignal.MIXED and action == CliAction.UNINSTALL:
        # Already handled above (MIXED + uninstall with force check).
        return

    # All ProviderDirSignal values are handled above.
    logger.warning("Unknown ProviderDirSignal member: %s (action=%s)", signal, action)


# ---------------------------------------------------------------------------
# Content rules
# ---------------------------------------------------------------------------


def _resolve_content(
    plan: ResolutionPlan,
    content: dict[str, ContentSignal],
    tool_name: str,
    action: CliAction,
    *,
    force: bool,
) -> None:
    """Apply per-resource content resolution rules for a single provider."""
    if action != CliAction.SYNC:
        return

    for resource, signal in content.items():
        if signal == ContentSignal.CLEAN:
            continue

        if signal == ContentSignal.STALE:
            if force:
                plan.steps.append(
                    ResolutionStep(
                        action=ResolutionAction.PRUNE,
                        target=f"{tool_name}:{resource}",
                        reason=f"Stale file '{resource}' has no source",
                    )
                )
            else:
                plan.warnings.append(
                    f"Stale file '{resource}' in '{tool_name}' has no source. "
                    f"Use --force to prune."
                )

        elif signal == ContentSignal.MISSING:
            plan.steps.append(
                ResolutionStep(
                    action=ResolutionAction.SYNC,
                    target=f"{tool_name}:{resource}",
                    reason=f"Missing file '{resource}' in '{tool_name}'",
                )
            )

        elif signal == ContentSignal.DIVERGED:
            if force:
                plan.steps.append(
                    ResolutionStep(
                        action=ResolutionAction.SYNC,
                        target=f"{tool_name}:{resource}",
                        reason=(
                            f"Overwriting diverged file '{resource}' in '{tool_name}'"
                        ),
                    )
                )
            else:
                plan.warnings.append(
                    f"File '{resource}' in '{tool_name}' has diverged from source. "
                    f"Use --force to overwrite."
                )

        else:
            # All ContentSignal values are handled above.
            logger.warning(
                "Unknown ContentSignal member: %s (action=%s)", signal, action
            )


# ---------------------------------------------------------------------------
# Builtin version rules
# ---------------------------------------------------------------------------


def _resolve_builtin_version(
    plan: ResolutionPlan,
    signal: BuiltinVersionSignal,
    action: CliAction,
    *,
    force: bool,
) -> None:
    """Apply builtin-version resolution rules."""
    if signal == BuiltinVersionSignal.CURRENT:
        return

    if signal == BuiltinVersionSignal.DELETED:
        plan.warnings.append(
            "Builtin resources have been deleted from .vaultspec/. "
            "Run 'vaultspec-core install --upgrade' to restore."
        )
        if force and action == CliAction.SYNC:
            plan.steps.append(
                ResolutionStep(
                    action=ResolutionAction.SYNC,
                    target="builtins",
                    reason="Re-seed deleted builtin resources",
                )
            )
        return

    if signal == BuiltinVersionSignal.NO_SNAPSHOTS:
        # install / install --upgrade write the snapshot themselves, so a
        # missing baseline is not actionable for them. Only a plain sync
        # against a snapshot-less workspace needs the operator warned.
        if action == CliAction.SYNC:
            plan.warnings.append(
                "No version baseline for builtins - cannot verify integrity. "
                "Run 'vaultspec-core install --upgrade' to establish baseline."
            )
        return

    if signal == BuiltinVersionSignal.MODIFIED and action == CliAction.SYNC:
        if force:
            plan.steps.append(
                ResolutionStep(
                    action=ResolutionAction.SYNC,
                    target="builtins",
                    reason="Re-seeding modified builtins",
                )
            )
        else:
            plan.warnings.append(
                "Builtin files have been modified since install. "
                "Use --force to re-seed."
            )
        return

    if signal == BuiltinVersionSignal.MODIFIED and action in (
        CliAction.INSTALL,
        CliAction.UNINSTALL,
    ):
        # Modified builtins during install: vaultspec-core install --upgrade re-seeds.
        # Modified builtins during uninstall: they'll be removed anyway.
        return

    if signal == BuiltinVersionSignal.DELETED and action in (
        CliAction.INSTALL,
        CliAction.UNINSTALL,
    ):
        # Deleted during install: vaultspec-core install --upgrade re-seeds.
        # Deleted during uninstall: nothing left to remove.
        return

    # All BuiltinVersionSignal values are handled above.
    logger.warning(
        "Unknown BuiltinVersionSignal member: %s (action=%s)", signal, action
    )


# ---------------------------------------------------------------------------
# Config rules
# ---------------------------------------------------------------------------


_ROOT_CONFIG_LABELS = {
    "claude": "CLAUDE.md",
    "gemini": "GEMINI.md",
    "antigravity": "GEMINI.md",
    "codex": "AGENTS.md",
}


def _resolve_config(
    plan: ResolutionPlan,
    signal: ConfigSignal,
    tool_name: str,
    action: CliAction,
    *,
    force: bool,
) -> None:
    """Apply config resolution rules for a single provider."""
    if action != CliAction.SYNC:
        return

    if signal in (
        ConfigSignal.OK,
        ConfigSignal.PARTIAL_MCP,
        ConfigSignal.USER_MCP,
        ConfigSignal.REGISTRY_DRIFT,
    ):
        return

    if signal == ConfigSignal.MISSING:
        plan.steps.append(
            ResolutionStep(
                action=ResolutionAction.SYNC,
                target=f"{tool_name}:config",
                reason=(
                    f"Root config {_ROOT_CONFIG_LABELS.get(tool_name, 'config file')} "
                    f"missing for provider '{tool_name}'"
                ),
            )
        )
        return

    if signal == ConfigSignal.FOREIGN:
        if force:
            plan.steps.append(
                ResolutionStep(
                    action=ResolutionAction.SYNC,
                    target=f"{tool_name}:config",
                    reason=(
                        "Overwriting user-authored root config "
                        f"{_ROOT_CONFIG_LABELS.get(tool_name, 'config file')} "
                        f"for provider '{tool_name}'"
                    ),
                )
            )
        else:
            plan.warnings.append(
                f"Config for '{tool_name}' appears user-authored. "
                f"Use --force to overwrite."
            )
        return

    # Config resolution only applies to "sync" action; other actions handled
    # by the main command directly.  All ConfigSignal values covered above.
    logger.warning("Unknown ConfigSignal member: %s (action=%s)", signal, action)


# ---------------------------------------------------------------------------
# Gitignore rules
# ---------------------------------------------------------------------------


def _resolve_gitignore(
    plan: ResolutionPlan,
    signal: GitignoreSignal,
    action: CliAction,
    *,
    force: bool,
) -> None:
    """Apply gitignore resolution rules."""
    _ = force  # gitignore repairs are unconditional
    if signal in (GitignoreSignal.COMPLETE, GitignoreSignal.NO_FILE):
        return

    if signal == GitignoreSignal.PARTIAL:
        if action in (CliAction.INSTALL, CliAction.SYNC):
            plan.steps.append(
                ResolutionStep(
                    action=ResolutionAction.REPAIR_GITIGNORE,
                    target=".gitignore",
                    reason="Managed block entries are stale, updating",
                )
            )
        return

    if signal == GitignoreSignal.CORRUPTED:
        plan.steps.append(
            ResolutionStep(
                action=ResolutionAction.REPAIR_GITIGNORE,
                target=".gitignore",
                reason="Gitignore managed block is corrupted",
            )
        )
        return

    if signal == GitignoreSignal.NO_ENTRIES and action == CliAction.INSTALL:
        plan.steps.append(
            ResolutionStep(
                action=ResolutionAction.REPAIR_GITIGNORE,
                target=".gitignore",
                reason="Gitignore has no managed entries",
            )
        )
        return

    if signal == GitignoreSignal.NO_ENTRIES and action in (
        CliAction.SYNC,
        CliAction.UNINSTALL,
    ):
        # No managed entries during sync/uninstall: no action needed.
        # Sync will not add gitignore entries (that's install's job).
        # Uninstall doesn't need entries that aren't there.
        return

    if signal == GitignoreSignal.PARTIAL and action == CliAction.UNINSTALL:
        # Partial entries during uninstall: the managed block will be
        # removed by the uninstall command.
        return


# ---------------------------------------------------------------------------
# Gitattributes rules
# ---------------------------------------------------------------------------


def _resolve_gitattributes(
    plan: ResolutionPlan,
    signal: GitattributesSignal,
    action: CliAction,
    *,
    force: bool,
) -> None:
    """Apply gitattributes resolution rules."""
    _ = force  # gitattributes repairs are unconditional
    if signal in (GitattributesSignal.COMPLETE, GitattributesSignal.NO_FILE):
        return

    if signal == GitattributesSignal.PARTIAL:
        if action in (CliAction.INSTALL, CliAction.SYNC):
            plan.steps.append(
                ResolutionStep(
                    action=ResolutionAction.REPAIR_GITATTRIBUTES,
                    target=".gitattributes",
                    reason="Managed block entries are stale, updating",
                )
            )
        return

    if signal == GitattributesSignal.CORRUPTED:
        plan.steps.append(
            ResolutionStep(
                action=ResolutionAction.REPAIR_GITATTRIBUTES,
                target=".gitattributes",
                reason="Gitattributes managed block is corrupted",
            )
        )
        return

    if signal == GitattributesSignal.NO_ENTRIES and action == CliAction.INSTALL:
        plan.steps.append(
            ResolutionStep(
                action=ResolutionAction.REPAIR_GITATTRIBUTES,
                target=".gitattributes",
                reason="Gitattributes has no managed entries",
            )
        )
        return

    if signal == GitattributesSignal.NO_ENTRIES and action in (
        CliAction.SYNC,
        CliAction.UNINSTALL,
    ):
        return

    if signal == GitattributesSignal.PARTIAL and action == CliAction.UNINSTALL:
        return

    # All GitattributesSignal values are handled above.
    logger.warning("Unknown GitattributesSignal member: %s (action=%s)", signal, action)


# ---------------------------------------------------------------------------
# Pre-commit hooks
# ---------------------------------------------------------------------------


def _resolve_precommit(
    plan: ResolutionPlan,
    signal: PrecommitSignal,
    action: CliAction,
    *,
    force: bool,
    precommit_managed: bool = True,
    expected_entry_prefix: str = "uv run --no-sync vaultspec-core",
) -> None:
    """Apply pre-commit hook resolution rules."""
    _ = force  # precommit repairs are unconditional
    if not precommit_managed:
        return
    if signal == PrecommitSignal.COMPLETE:
        return

    if signal == PrecommitSignal.NO_FILE:
        if precommit_managed and action == CliAction.SYNC:
            plan.steps.append(
                ResolutionStep(
                    action=ResolutionAction.REPAIR_PRECOMMIT,
                    target=".pre-commit-config.yaml",
                    reason="Pre-commit config missing but management is enabled",
                )
            )
        return

    if signal == PrecommitSignal.NO_HOOKS:
        if action in (CliAction.INSTALL, CliAction.SYNC):
            plan.steps.append(
                ResolutionStep(
                    action=ResolutionAction.REPAIR_PRECOMMIT,
                    target=".pre-commit-config.yaml",
                    reason="No vaultspec-core hooks found in pre-commit config",
                )
            )
        return

    if signal == PrecommitSignal.INCOMPLETE:
        if action in (CliAction.INSTALL, CliAction.SYNC):
            plan.steps.append(
                ResolutionStep(
                    action=ResolutionAction.REPAIR_PRECOMMIT,
                    target=".pre-commit-config.yaml",
                    reason="Missing canonical hooks in pre-commit config",
                )
            )
        return

    if signal == PrecommitSignal.NON_CANONICAL:
        if action in (CliAction.INSTALL, CliAction.SYNC):
            plan.steps.append(
                ResolutionStep(
                    action=ResolutionAction.REPAIR_PRECOMMIT,
                    target=".pre-commit-config.yaml",
                    reason=(
                        "Hook entries use non-canonical pattern; "
                        f"should use '{expected_entry_prefix}'"
                    ),
                )
            )
        return

    logger.warning("Unknown PrecommitSignal member: %s (action=%s)", signal, action)


# ---------------------------------------------------------------------------
# Install-mode mismatch
# ---------------------------------------------------------------------------


def _resolve_mode_mismatch(
    plan: ResolutionPlan,
    signal: ModeMismatchSignal,
) -> None:
    """Warn when provisioned artifacts disagree with the declared install mode.

    A :attr:`~vaultspec_core.core.diagnosis.signals.ModeMismatchSignal.MISMATCH`
    means the committed declaration names one mode but the deployed hook entries
    or MCP launch command are shaped for the other. This is advisory rather than
    auto-repaired: reconciling it re-provisions the workspace, which is an
    explicit operator decision, so the plan carries a fix hint pointing at
    ``install --upgrade`` or an explicit ``--mode`` re-run rather than a silent
    corrective step. ``CLEAN`` and ``UNKNOWN`` (the legacy, undeclared workspace)
    are no-ops.
    """
    if signal != ModeMismatchSignal.MISMATCH:
        return
    plan.warnings.append(
        "Provisioned hook entries or MCP launch command do not match the "
        "install mode declared in .vaultspec/workspace.json. Re-run "
        "'vaultspec-core install --upgrade' to reconcile them, or "
        "'vaultspec-core install --mode <tool|dependency>' to re-provision "
        "for a specific mode."
    )


# ---------------------------------------------------------------------------
# Version mismatch warning
# ---------------------------------------------------------------------------


def _enforce_version_floor(target: Path, running_version: str) -> None:
    """Refuse when the running version is below the workspace floor constraint.

    Reads the committed ``.vaultspec/workspace.json`` declaration's
    ``minimum_vaultspec_version`` and hard-refuses, refuse-and-tell per the
    pre-commit/Terraform precedent, when the running package version is below
    it. A workspace that declares no floor, or whose declaration cannot be read,
    imposes no constraint. This is the hard guarantee tool mode leans on once
    the running CLI and the hooks/MCP runtime are no longer the same install;
    the softer manifest-stamp warning below remains an informational drift
    signal beneath it.

    Args:
        target: Workspace root directory.
        running_version: The running ``vaultspec-core`` package version string.

    Raises:
        VaultSpecError: When the running version is below the declared floor.
    """
    from .exceptions import VaultSpecError
    from .workspace_mode import read_workspace_declaration

    try:
        declaration = read_workspace_declaration(target)
    except VaultSpecError:
        # A corrupt declaration surfaces through the explicit install/mode
        # paths that must refuse on it; do not raise a second, differently
        # shaped error from the version-check area.
        logger.debug("Could not read declaration for floor check", exc_info=True)
        return

    if declaration is None or declaration.minimum_vaultspec_version is None:
        return

    floor = declaration.minimum_vaultspec_version
    try:
        running_parts = parse_version_tuple(running_version)
        floor_parts = parse_version_tuple(floor)
    except Exception:
        logger.debug("Could not parse versions for floor check", exc_info=True)
        return

    if running_parts < floor_parts:
        raise VaultSpecError(
            f"vaultspec-core {running_version} is below the workspace floor "
            f"{floor} declared in .vaultspec/workspace.json.",
            hint=(
                f"Upgrade to at least {floor}: 'uv tool upgrade vaultspec-core' "
                f"(or 'uv sync --upgrade-package vaultspec-core' when used as a "
                f"project dependency)."
            ),
        )


def _resolve_version_warning(
    plan: ResolutionPlan,
    diagnosis: WorkspaceDiagnosis,
) -> None:
    """Emit a warning if the manifest was written by a newer vaultspec-core."""
    if diagnosis.framework != FrameworkSignal.PRESENT:
        return

    try:
        from importlib.metadata import version as pkg_version

        running_version = pkg_version("vaultspec-core")
    except Exception:
        logger.debug(
            "Could not determine running vaultspec-core version",
            exc_info=True,
        )
        return

    try:
        from .types import get_context

        target = get_context().target_dir
    except LookupError:
        logger.debug("No workspace context available for version check", exc_info=True)
        return

    # Hard floor constraint first: a running version below the declared
    # minimum refuses outright, before the softer manifest-stamp drift warning.
    _enforce_version_floor(target, running_version)

    try:
        from .manifest import read_manifest_data

        manifest = read_manifest_data(target)
    except Exception:
        logger.debug("Could not read manifest for version check", exc_info=True)
        return

    manifest_version = manifest.vaultspec_version
    if not manifest_version:
        return

    # Compare using tuple of parsed version segments
    try:
        running_parts = parse_version_tuple(running_version)
        manifest_parts = parse_version_tuple(manifest_version)

        # A bundled migration legitimately stamps the manifest to its own
        # target_version, which can exceed the running package version (e.g.
        # 0.1.20 shipped a migration tagged 0.1.21). Gating the advisory on the
        # package version alone then points users at a release that does not
        # exist on PyPI, an unresolvable warning (issue #119). Raise the
        # threshold to the highest version this package actually knows about:
        # the greater of the running version and the highest registered
        # migration target. Only a manifest beyond that genuinely came from a
        # newer install and warrants the upgrade advisory.
        from ..migrations import REGISTRY

        known_ceiling = running_parts
        for migration in REGISTRY:
            target_parts = parse_version_tuple(migration.target_version)
            if target_parts > known_ceiling:
                known_ceiling = target_parts

        if manifest_parts > known_ceiling:
            plan.warnings.append(
                f"Manifest was written by vaultspec-core {manifest_version}, "
                f"but running version is {running_version}. "
                f"Consider upgrading: uv tool upgrade vaultspec-core "
                f"(or `uv sync --upgrade-package vaultspec-core` if used "
                f"as a project dependency)"
            )
    except Exception:
        logger.debug("Version comparison failed", exc_info=True)


if TYPE_CHECKING:
    from .diagnosis.diagnosis import WorkspaceDiagnosis
