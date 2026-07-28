"""Framework-level resolution rules.

Covers the top-of-matrix :class:`~vaultspec_core.core.diagnosis.signals.FrameworkSignal`
checks: a missing framework, a corrupted manifest, and the tracked-but-unmanifested
"adoptable" state. Split out of ``resolver.py`` as the first rule group the
orchestrator evaluates.
"""

from __future__ import annotations

import logging

from .diagnosis.signals import FrameworkSignal, ResolutionAction
from .enums import CliAction
from .resolver_types import ResolutionPlan, ResolutionStep

logger = logging.getLogger(__name__)

__all__ = ["resolve_framework"]

#: The actions the framework rules act on. An action outside this set falls
#: through to the unhandled-signal warning, whatever the signal.
_FRAMEWORK_ACTIONS = (CliAction.INSTALL, CliAction.SYNC, CliAction.UNINSTALL)

#: Cap on the number of diverged paths spelled out in the adoption conflict.
#: The list must be precise enough to act on without becoming an unreadable
#: wall of text on a workspace that has drifted wholesale.
_MAX_LISTED_DIVERGENCES = 20


def resolve_framework(
    plan: ResolutionPlan,
    signal: FrameworkSignal,
    action: CliAction,
    *,
    force: bool,
    divergent_projections: list[str] | None = None,
) -> None:
    """Apply framework-level resolution rules."""
    if signal == FrameworkSignal.PRESENT:
        return

    if signal == FrameworkSignal.ADOPTABLE:
        _resolve_adoptable(
            plan, action, force=force, divergent_projections=divergent_projections or []
        )
        return

    if signal == FrameworkSignal.MISSING and action in _FRAMEWORK_ACTIONS:
        _resolve_framework_missing(plan, action)
        return

    if signal == FrameworkSignal.CORRUPTED and action in _FRAMEWORK_ACTIONS:
        _resolve_framework_corrupted(plan, action, force=force)
        return

    # All FrameworkSignal values are handled above; this is unreachable
    # unless a new enum member is added without updating the resolver.
    logger.warning("Unknown FrameworkSignal member: %s (action=%s)", signal, action)


def _resolve_framework_missing(plan: ResolutionPlan, action: CliAction) -> None:
    """Apply resolution rules for a workspace with no framework installed."""
    if action == CliAction.SYNC:
        plan.conflicts.append(
            "Framework not installed. Run 'vaultspec-core install' first."
        )
    elif action == CliAction.UNINSTALL:
        plan.warnings.append("Nothing to remove - framework is not installed.")
    # Install proceeds normally - it will scaffold.


def _resolve_framework_corrupted(
    plan: ResolutionPlan,
    action: CliAction,
    *,
    force: bool,
) -> None:
    """Apply resolution rules for a corrupted framework manifest."""
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

    if action == CliAction.INSTALL:
        reason = "Manifest corrupted, repairing before install"
        conflict = "Manifest is corrupted. Use --force to repair."
    elif action == CliAction.UNINSTALL:
        reason = "Corrupted manifest - repairing before uninstall"
        conflict = "Manifest is corrupted. Use --force to proceed with uninstall."
    else:
        return

    if force:
        plan.steps.append(
            ResolutionStep(
                action=ResolutionAction.REPAIR_MANIFEST,
                target="manifest",
                reason=reason,
            )
        )
    else:
        plan.conflicts.append(conflict)


def _resolve_adoptable(
    plan: ResolutionPlan,
    action: CliAction,
    *,
    force: bool,
    divergent_projections: list[str],
) -> None:
    """Apply resolution rules for a tracked-but-unmanifested framework.

    Establishing the runtime manifest is a create-only operation: it writes one
    file that did not exist and overwrites nothing, which the framework-wide
    gating contract classifies as an additive path requiring no ``--force``.
    That is what makes a fresh clone adoptable in one ordinary run.

    The adopting run's provider sync is the mixed path. Its per-file writes are
    not force-gated, so any projection whose on-disk content has diverged from
    source would be rewritten. On a workspace vaultspec has never claimed
    locally that content is the operator's, not ours, so the destructive
    sub-path is gated independently: adoption refuses with the exact paths named
    and ``--force`` as the explicit consent.
    """
    if action == CliAction.UNINSTALL:
        # Uninstall needs to know what is installed before it removes anything.
        # Adoption is additive, so it runs unconditionally here; uninstall's own
        # gating continues to govern the removal itself.
        plan.steps.append(
            ResolutionStep(
                action=ResolutionAction.ADOPT_FRAMEWORK,
                target="manifest",
                reason="Establishing runtime manifest before uninstall",
            )
        )
        return

    if divergent_projections and not force:
        listed = divergent_projections[:_MAX_LISTED_DIVERGENCES]
        remainder = len(divergent_projections) - len(listed)
        detail = ", ".join(listed)
        if remainder > 0:
            detail += f", and {remainder} more"
        plan.conflicts.append(
            "Cannot adopt this workspace without overwriting locally divergent "
            f"projected content: {detail}. Reconcile these files with their "
            ".vaultspec/ sources, or re-run with --force to overwrite them."
        )
        return

    plan.steps.append(
        ResolutionStep(
            action=ResolutionAction.ADOPT_FRAMEWORK,
            target="manifest",
            reason=(
                "Framework content present without a runtime manifest; "
                "establishing manifest state"
            ),
        )
    )
    if action == CliAction.SYNC:
        plan.steps.append(
            ResolutionStep(
                action=ResolutionAction.SYNC,
                target="all",
                reason="Sync after adopting the framework",
            )
        )
