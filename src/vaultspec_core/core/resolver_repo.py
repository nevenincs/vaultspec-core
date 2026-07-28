"""Repository config file resolution rules.

Covers the three managed repo-root files the orchestrator reconciles once per
run: ``.gitignore``, ``.gitattributes``, and the pre-commit hook config. Split
out of ``resolver.py`` as the cross-cutting, non-provider-scoped rule group.
"""

from __future__ import annotations

import logging

from .diagnosis.signals import (
    GitattributesSignal,
    GitignoreSignal,
    PrecommitSignal,
    ResolutionAction,
)
from .enums import CliAction
from .resolver_types import ResolutionPlan, ResolutionStep

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Gitignore rules
# ---------------------------------------------------------------------------


def resolve_gitignore(
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


# ---------------------------------------------------------------------------
# Gitattributes rules
# ---------------------------------------------------------------------------


def resolve_gitattributes(
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

    # All GitattributesSignal values are handled above.
    logger.warning("Unknown GitattributesSignal member: %s (action=%s)", signal, action)


# ---------------------------------------------------------------------------
# Pre-commit hooks
# ---------------------------------------------------------------------------


#: Repair reason per pre-commit signal, for the signals install and sync can
#: repair in place. ``{entry_prefix}`` is filled with the mode-appropriate
#: canonical hook entry prefix. NO_FILE is absent: scaffolding an entirely
#: missing config is a sync-only repair with its own reason.
_PRECOMMIT_REPAIR_REASONS: dict[PrecommitSignal, str] = {
    PrecommitSignal.NO_HOOKS: "No vaultspec-core hooks found in pre-commit config",
    PrecommitSignal.INCOMPLETE: "Missing canonical hooks in pre-commit config",
    PrecommitSignal.NON_CANONICAL: (
        "Hook entries use non-canonical pattern; should use '{entry_prefix}'"
    ),
}

#: Signals that describe a coherent boundary no resolution step acts on.
#: UNREFRESHABLE means ``prek.toml`` owns the boundary and lacks the canonical
#: hooks, so sync cannot repair anything - the doctor surface renders the
#: actionable advisory (``spec precommit migrate``) instead. ORPHANED means the
#: hooks live safely in ``prek.toml`` and the leftover
#: ``.pre-commit-config.yaml`` is superseded and operator-owned; removal is
#: operator-gated, never a sync-time repair.
_PRECOMMIT_INERT_SIGNALS = (
    PrecommitSignal.COMPLETE,
    PrecommitSignal.UNREFRESHABLE,
    PrecommitSignal.ORPHANED,
)


def resolve_precommit(
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
    if signal in _PRECOMMIT_INERT_SIGNALS:
        return

    if signal == PrecommitSignal.NO_FILE:
        if action == CliAction.SYNC:
            plan.steps.append(
                ResolutionStep(
                    action=ResolutionAction.REPAIR_PRECOMMIT,
                    target=".pre-commit-config.yaml",
                    reason="Pre-commit config missing but management is enabled",
                )
            )
        return

    reason = _PRECOMMIT_REPAIR_REASONS.get(signal)
    if reason is not None:
        if action in (CliAction.INSTALL, CliAction.SYNC):
            plan.steps.append(
                ResolutionStep(
                    action=ResolutionAction.REPAIR_PRECOMMIT,
                    target=".pre-commit-config.yaml",
                    reason=reason.format(entry_prefix=expected_entry_prefix),
                )
            )
        return

    logger.warning("Unknown PrecommitSignal member: %s (action=%s)", signal, action)
