"""Converge installed commit-hook configs on the single commit gate.

Introduced for vaultspec-core 0.2.5. Until this release the scaffolded hook
config carried ``vault-fix``, ``spec-check`` and ``check-provider-artifacts``
(and, earlier still, ``vault-sanitize-annotations``). Each ran on every commit,
two of them scanned the whole vault, and one rewrote it. They are replaced by
one ``vaultspec-commit-gate`` hook that checks only what a commit stages.

``sync`` already converges a config it manages, but only while the install
still manages it and only when someone runs ``sync``. This entry makes the
change part of the release itself: the registry's explicit triggers run it
once per workspace, and ``migrations status`` reports it as pending until
they do.

It is deliberately narrow about what it touches:

- a YAML hook config is converged only while it still carries vaultspec hooks,
  current or retired - including one whose install stopped managing it, which
  ``sync`` skips. Converging goes through the scaffold, so the operator's own
  hooks, comments and quoting survive;
- in a ``prek.toml`` workspace only an existing vaultspec-managed block is
  re-rendered. A block is never added: moving hooks into ``prek.toml`` is the
  operator's call through ``spec precommit migrate``;
- a workspace whose declaration declines the hooks, a config with no vaultspec
  hooks, and a workspace with no config at all are left exactly as they are.
  Nothing is created.

See also:
    :mod:`vaultspec_core.migrations` for the registry driver.
    :mod:`vaultspec_core.core.precommit` for the canonical hook set.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from . import Migration, MigrationResult, MigrationScope

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["MIGRATION", "migrate", "preview"]

logger = logging.getLogger(__name__)

_TARGET_VERSION = "0.2.5"
_NAME = "commit_gate"


def _result(summary: str, *, yaml: int = 0, prek: int = 0) -> MigrationResult:
    return MigrationResult(
        name=_NAME,
        target_version=_TARGET_VERSION,
        summary=summary,
        counts={"yaml": yaml, "prek": prek},
    )


def preview(workspace: Path) -> list[Path]:
    """Return every path this migration would delete: always none.

    Converging rewrites a hook config in place; it never removes one. The
    scaffold keeps a config even when vaultspec's hooks were all it held,
    because it writes the gate back in.

    Args:
        workspace: Workspace root directory.

    Returns:
        An empty list.
    """
    del workspace
    return []


def _converge_prek(workspace: Path) -> MigrationResult:
    """Re-render a stale managed block in ``prek.toml``; never add one."""
    from ..core.prek_boundary import collect_prek_boundary, refresh_managed_prek_block

    if collect_prek_boundary(workspace).parse_error:
        return _result("prek.toml could not be read; left for spec doctor")
    change = refresh_managed_prek_block(workspace)
    if change:
        return _result(f"{change} in prek.toml", prek=1)
    return _result("no stale vaultspec block in prek.toml; nothing converged")


def _converge_yaml(workspace: Path) -> MigrationResult:
    """Converge the YAML config prek reads, while it carries vaultspec hooks."""
    from ..core.precommit import managed_strip_outcome, scaffold_precommit
    from ..core.prek_boundary import precommit_config_path

    config = precommit_config_path(workspace)
    if not config.exists():
        return _result("no hook config; nothing converged")
    # ``managed_strip_outcome`` answers "does this config carry any vaultspec
    # hook, current or retired" without writing: a config it would leave
    # unchanged has none, which is an operator's decision to honour.
    outcome = managed_strip_outcome(config)
    if outcome == "unreadable":
        return _result(f"{config.name} could not be read; left for spec doctor")
    if outcome == "unchanged":
        return _result(f"{config.name} carries no vaultspec hooks; left as it is")
    if scaffold_precommit(workspace):
        summary = f"converged {config.name} on the vaultspec-commit-gate hook"
        logger.info("Migration %s: %s", _NAME, summary)
        return _result(summary, yaml=1)
    return _result(f"{config.name} already carries only the commit gate")


def migrate(workspace: Path) -> MigrationResult:
    """Replace retired vaultspec hooks with the commit gate where they remain.

    Args:
        workspace: Workspace root directory.

    Returns:
        :class:`MigrationResult` whose ``counts`` carries ``yaml`` (YAML
        configs converged) and ``prek`` (managed ``prek.toml`` blocks
        re-rendered).

    Raises:
        Nothing for an unreadable declaration or config: those are reported
        in the summary and left for ``spec doctor``, so one broken file never
        wedges the registry for every later entry.
    """
    from ..core.exceptions import VaultSpecError
    from ..core.prek_boundary import PREK_CONFIG_NAME
    from ..core.workspace_mode import read_hooks_declaration

    try:
        declined = not read_hooks_declaration(workspace).pre_commit
    except VaultSpecError as exc:
        logger.warning("Migration %s: %s", _NAME, exc)
        return _result("workspace declaration unreadable; left for spec doctor")
    if declined:
        return _result("the workspace declines commit hooks; nothing converged")
    if (workspace / PREK_CONFIG_NAME).exists():
        return _converge_prek(workspace)
    return _converge_yaml(workspace)


MIGRATION = Migration(
    target_version=_TARGET_VERSION,
    name=_NAME,
    migrate=migrate,
    preview=preview,
    # Host configuration, never a .vault/ document, and nothing about where an
    # authored document lands depends on it, so only the explicit convergence
    # triggers run it.
    scope=MigrationScope.ENVIRONMENT,
)
