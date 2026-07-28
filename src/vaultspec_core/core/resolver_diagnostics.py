"""Cross-cutting diagnostic resolution rules.

Covers checks that are neither framework- nor provider-scoped: builtin content
drift under ``.vaultspec/``, install-mode/provisioning mismatches, and the
running-version-vs-manifest advisory (including the hard version floor
refusal). Split out of ``resolver.py`` as the rule group evaluated once per run
regardless of provider.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from .diagnosis.signals import (
    BuiltinVersionSignal,
    FrameworkSignal,
    ModeMismatchSignal,
    ResolutionAction,
)
from .enums import CliAction
from .helpers import parse_version_tuple
from .resolver_types import ResolutionPlan, ResolutionStep

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .diagnosis.diagnosis import WorkspaceDiagnosis


# ---------------------------------------------------------------------------
# Builtin version rules
# ---------------------------------------------------------------------------


def resolve_builtin_version(
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
        if action in (CliAction.INSTALL, CliAction.UNINSTALL):
            # Deleted during install: vaultspec-core install --upgrade re-seeds.
            # Deleted during uninstall: nothing left to remove.
            return
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

    # All BuiltinVersionSignal values are handled above.
    logger.warning(
        "Unknown BuiltinVersionSignal member: %s (action=%s)", signal, action
    )


# ---------------------------------------------------------------------------
# Install-mode mismatch
# ---------------------------------------------------------------------------


def resolve_mode_mismatch(
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
    from .workspace_mode import evaluate_version_floor

    try:
        violation = evaluate_version_floor(target, running_version)
    except VaultSpecError:
        # A corrupt declaration surfaces through the explicit install/mode
        # paths that must refuse on it; do not raise a second, differently
        # shaped error from the version-check area.
        logger.debug("Could not read declaration for floor check", exc_info=True)
        return

    if violation is None:
        return

    running, floor = violation
    raise VaultSpecError(
        f"vaultspec-core {running} is below the workspace floor "
        f"{floor} declared in .vaultspec/workspace.json.",
        hint=(
            f"Upgrade to at least {floor}: 'uv tool upgrade vaultspec-core' "
            f"(or 'uv sync --upgrade-package vaultspec-core' when used as a "
            f"project dependency)."
        ),
    )


def resolve_version_warning(
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
