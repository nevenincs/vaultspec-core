"""Explicit MCP approval setup for tests of rendering and ownership.

Security tests call the production writer directly. Compatibility tests use
these helpers to model an operator who has reviewed their test definitions;
they still exercise the production ledger lookup and enrollment enforcement.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vaultspec_core.core.enums import InstallMode, McpScope, Tool
from vaultspec_core.core.mcps_definitions import collect_mcp_servers
from vaultspec_core.core.mcps_native import normalized_sources
from vaultspec_core.core.mcps_sync import mcp_sync
from vaultspec_core.core.mcps_targets import resolve_mcp_targets
from vaultspec_core.core.mcps_trust import McpApproval, grant
from vaultspec_core.core.types import SyncResult, get_context
from vaultspec_core.core.workspace_mode import (
    CORE_DISTRIBUTION_NAME,
    resolve_render_mode,
)

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

__all__ = ["approve_mcp_definitions", "approved_mcp_sync"]


def approve_mcp_definitions(
    root: Path,
    *,
    provider: Tool | str = "all",
    scope: McpScope | str = McpScope.PROJECT,
    mode: InstallMode | None = None,
    enrolled: Iterable[Tool] | None = None,
) -> None:
    """Record real host-local grants for the current test launch snapshots."""
    mode = mode or resolve_render_mode(root, package=CORE_DISTRIBUTION_NAME)
    digests: dict[Path, str] = {}
    sources = collect_mcp_servers(mode=mode, target=root, digests=digests)
    approvals: list[McpApproval] = []
    for target in resolve_mcp_targets(
        provider, scope=scope, target_dir=root, enrolled=enrolled
    ):
        normalized = normalized_sources(sources, target, SyncResult())
        approvals.extend(
            McpApproval.capture(root, target, name, path, config, digests[path])
            for name, (path, config) in normalized.items()
        )
    if approvals:
        grant(approvals)


def approved_mcp_sync(
    dry_run: bool = False,
    force: bool = False,
    prune: bool = False,
    mode: InstallMode | None = None,
    force_managed: frozenset[str] = frozenset(),
    *,
    provider: Tool | str = "all",
    scope: McpScope | str = McpScope.PROJECT,
    target_dir: Path | None = None,
    enrolled: Iterable[Tool] | None = None,
) -> SyncResult:
    """Model explicit approval before testing the existing reconciliation rules."""
    from vaultspec_core.core.exceptions import VaultSpecError

    try:
        root = target_dir or get_context().target_dir
        approve_mcp_definitions(
            root, provider=provider, scope=scope, mode=mode, enrolled=enrolled
        )
    except (LookupError, VaultSpecError):
        # Invalid target/context tests should observe the real writer's errors.
        pass
    return mcp_sync(
        dry_run=dry_run,
        force=force,
        prune=prune,
        mode=mode,
        force_managed=force_managed,
        provider=provider,
        scope=scope,
        target_dir=target_dir,
        enrolled=enrolled,
    )
