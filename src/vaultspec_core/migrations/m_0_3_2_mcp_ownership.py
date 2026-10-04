"""Retire repository MCP ownership claims without promoting their authority.

Version 0.3.2 stores ownership in the operator's home, bound to canonical
workspace and target paths. Repository fingerprints cannot prove prior local
management, so importing them would preserve the vulnerability. This migration
removes only the obsolete sidecar; host configurations and trusted ownership
remain untouched. Existing entries require explicit review and adoption.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from . import Migration, MigrationError, MigrationResult, MigrationScope
from ._paths import check_path

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["MIGRATION", "migrate", "preview"]

_TARGET_VERSION = "0.3.2"
_NAME = "mcp_ownership"


def preview(workspace: Path) -> list[Path]:
    """Plan removal of the obsolete sidecar, rejecting linked paths."""
    path = workspace / ".vaultspec" / "mcp-ownership.json"
    check_path(workspace, path)
    if not path.exists():
        return []
    if not path.is_file():
        raise MigrationError(f"MCP ownership sidecar is not a file: {path}")
    return [path]


def migrate(workspace: Path) -> MigrationResult:
    """Discard repository claims without reading or importing their records."""
    paths = preview(workspace)
    for path in paths:
        path.unlink()
    summary = "no repository MCP ownership sidecar; nothing to retire"
    if paths:
        summary = (
            "retired repository MCP ownership claims; MCP configurations preserved; "
            "review and approve definitions, then use spec mcps sync --force "
            "to adopt existing entries explicitly"
        )
    return MigrationResult(
        name=_NAME,
        target_version=_TARGET_VERSION,
        summary=summary,
        counts={"retired": len(paths)},
    )


MIGRATION = Migration(
    target_version=_TARGET_VERSION,
    name=_NAME,
    migrate=migrate,
    preview=preview,
    scope=MigrationScope.ENVIRONMENT,
)
