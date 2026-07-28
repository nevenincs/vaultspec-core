"""Shared pre-flight diagnosis-and-resolution helper.

Defines :func:`_run_preflight`, used by the ``install``, ``uninstall``, and
``sync`` commands (:mod:`.root_install`, :mod:`.root_sync`) to run
preflight-safe resolution steps and display their outcomes before the main
command body executes.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import typer

from vaultspec_core.cli._errors import handle_error as _handle_error

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

# ``_run_preflight`` is consumed by :mod:`.root_install`, :mod:`.root_sync`,
# and :mod:`.root` under this module's leading-underscore convention for a
# shared-but-internal helper; the explicit re-export marks that cross-module
# contract for the type checker.
__all__ = ["_run_preflight"]


def _run_preflight(
    target: Path,
    action: str,
    provider: str = "all",
    *,
    force: bool = False,
    dry_run: bool = False,
    scope: str = "framework",
    render: bool = True,
) -> None:
    """Run diagnosis and resolution pre-flight.

    Executes preflight-safe resolution steps (manifest repair, gitignore
    repair, scaffold, adopt) and displays their outcomes. Non-preflight
    steps are shown as informational. Blocks on conflicts unless
    *dry_run* is ``True``.

    Raises :class:`typer.Exit` with code 1 if conflicts are present and
    *dry_run* is ``False``, or if any preflight execution step fails.
    """
    from vaultspec_core.core.diagnosis import diagnose
    from vaultspec_core.core.exceptions import VaultSpecError
    from vaultspec_core.core.executor import PREFLIGHT_ACTIONS, execute_plan
    from vaultspec_core.core.resolver import resolve

    try:
        diag = diagnose(target, scope=scope)
    except Exception:
        logger.warning("Pre-flight diagnosis failed", exc_info=True)
        return

    # resolve() raises a typed VaultSpecError for a refuse-and-tell condition
    # such as the below-floor version constraint. Route it through the same
    # clean error path the downstream mutating calls use rather than letting a
    # raw traceback escape preflight. render is the human-console flag, so its
    # inverse selects the machine-readable json error envelope.
    try:
        plan = resolve(diag, action, provider, force=force, dry_run=dry_run)
    except (VaultSpecError, OSError) as exc:
        _handle_error(exc, json_output=not render)
        return  # unreachable: _handle_error raises typer.Exit

    if not plan.warnings and not plan.conflicts and not plan.steps:
        return

    console = None
    if render:
        from vaultspec_core.console import get_console

        console = get_console()

    for warning in plan.warnings:
        if console:
            console.print(f"  [yellow]![/yellow] {warning}")

    # Execute preflight-safe resolution steps
    if plan.steps and not plan.blocked:
        exec_result = execute_plan(plan, target, dry_run=dry_run)

        for sr in exec_result.results:
            if not console:
                continue
            if sr.success:
                console.print(f"  [green]ok[/green] {sr.step.reason}")
            else:
                console.print(f"  [red]x[/red] {sr.step.reason}: {sr.error}")

        if exec_result.failed and not dry_run:
            raise typer.Exit(code=1)

    # Show non-preflight steps as informational (deferred to the main command)
    non_preflight = [s for s in plan.steps if s.action not in PREFLIGHT_ACTIONS]
    for step in non_preflight:
        if console:
            console.print(
                f"  [dim]>[/dim] {step.reason} "
                f"(detected, will be addressed by {action})"
            )

    if plan.conflicts:
        if console:
            console.print()
            for conflict in plan.conflicts:
                console.print(f"  [red]x[/red] {conflict}")
            console.print()
        if not dry_run:
            raise typer.Exit(code=1)
