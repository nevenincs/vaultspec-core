"""Resolution engine that maps diagnosed workspace state to corrective actions.

Takes a :class:`~vaultspec_core.core.diagnosis.WorkspaceDiagnosis` and a
requested CLI action, then produces a :class:`ResolutionPlan` of ordered steps,
warnings, and blocking conflicts. Follows the rule matrix defined in the
cli-ambiguous-states ADR.

The rule matrix is split by domain into sibling ``resolver_*`` modules; this
module is the public surface and orchestrator, re-exporting everything
callers import from ``vaultspec_core.core.resolver``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from .enums import CliAction
from .resolver_diagnostics import (
    resolve_builtin_version,
    resolve_mode_mismatch,
    resolve_version_warning,
)
from .resolver_framework import resolve_framework
from .resolver_providers import (
    resolve_config,
    resolve_content,
    resolve_manifest_entry,
    resolve_provider_dir,
)
from .resolver_repo import (
    resolve_gitattributes,
    resolve_gitignore,
    resolve_precommit,
)
from .resolver_types import ResolutionPlan, ResolutionStep

__all__ = [
    "ResolutionPlan",
    "ResolutionStep",
    "resolve",
]

logger = logging.getLogger(__name__)


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

    resolve_framework(
        plan,
        diagnosis.framework,
        fw_action,
        force=force,
        divergent_projections=diagnosis.divergent_projections,
    )
    resolve_version_warning(plan, diagnosis)
    # Builtins live directly under .vaultspec/ - framework content. Under
    # `install --upgrade` they are re-seeded unconditionally, so the
    # builtin-version signal must resolve with framework semantics; using
    # prov_action (SYNC) would wrongly tell the operator to pass --force
    # to re-seed something the upgrade is already about to re-seed.
    resolve_builtin_version(plan, diagnosis.builtin_version, fw_action, force=force)
    resolve_gitignore(plan, diagnosis.gitignore, prov_action, force=force)
    resolve_gitattributes(plan, diagnosis.gitattributes, prov_action, force=force)

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

    resolve_precommit(
        plan,
        diagnosis.precommit,
        prov_action,
        force=force,
        precommit_managed=pc_managed,
        expected_entry_prefix=expected_entry_prefix,
    )
    resolve_mode_mismatch(plan, diagnosis.mode_mismatch)

    # Per-provider rules
    for tool, prov_diag in diagnosis.providers.items():
        if provider != "all" and tool.value != provider:
            continue
        name = tool.value
        resolve_manifest_entry(
            plan,
            prov_diag.manifest_entry,
            name,
            prov_action,
            force=force,
        )
        resolve_provider_dir(
            plan,
            prov_diag.dir_state,
            name,
            prov_action,
            force=force,
        )
        resolve_content(
            plan,
            prov_diag.content,
            name,
            prov_action,
            force=force,
        )
        resolve_config(
            plan,
            prov_diag.config,
            name,
            prov_action,
            force=force,
        )

    return plan


if TYPE_CHECKING:
    from .diagnosis.diagnosis import WorkspaceDiagnosis
