"""Config file and repository-metadata collectors.

Assesses the state of a provider's root configuration file, the deployed
``.mcp.json`` registry, generated template annotations left in ``.vault/``,
and the vaultspec-managed blocks in ``.gitignore`` and ``.gitattributes``. All
imports from ``core.*`` modules are deferred inside function bodies to
prevent import cycles.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from .signals import (
    ConfigSignal,
    GitattributesSignal,
    GitignoreSignal,
    VaultContentSignal,
)

if TYPE_CHECKING:
    from ..enums import Tool

logger = logging.getLogger(__name__)


def _provider_config_file(tool: Tool) -> Path | None:
    """Return a provider's root config file path, or ``None`` when unresolvable."""
    from ..types import get_context

    try:
        ctx = get_context()
        cfg = ctx.tool_configs.get(tool)
    except LookupError:
        return None

    return cfg.config_file if cfg is not None else None


def collect_config_state(tool_value: str) -> ConfigSignal:
    """Assess the state of a provider's root configuration file.

    Args:
        tool_value: The :class:`~vaultspec_core.core.enums.Tool` ``.value``
            string (e.g. ``"claude"``).

    Returns:
        :class:`~vaultspec_core.core.diagnosis.signals.ConfigSignal`
        reflecting the observed state.
    """
    from ..enums import Tool

    config_file = _provider_config_file(Tool(tool_value))
    if config_file is None or not config_file.exists():
        return ConfigSignal.MISSING

    try:
        content = config_file.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Cannot read config %s: %s", config_file, exc)
        return ConfigSignal.MISSING

    # Detect both legacy AUTO-GENERATED header and current <vaultspec> tags
    if "AUTO-GENERATED" in content or "<vaultspec " in content:
        return ConfigSignal.OK

    return ConfigSignal.FOREIGN


# Shared with :mod:`vaultspec_core.core.diagnosis.collectors_mode`.
def read_mcp_servers(mcp_path: Path) -> dict[str, object] | None:
    """Return the ``mcpServers`` mapping from an ``.mcp.json`` file.

    Args:
        mcp_path: Path to the MCP configuration file.

    Returns:
        The deployed server entries, or ``None`` when the file is absent,
        unreadable, or does not carry a ``mcpServers`` mapping.
    """
    if not mcp_path.exists():
        return None

    try:
        raw = json.loads(mcp_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Cannot read MCP config %s: %s", mcp_path, exc)
        return None

    if not isinstance(raw, dict):
        return None

    raw_dict = cast("dict[str, object]", raw)
    servers = raw_dict.get("mcpServers")
    if not isinstance(servers, dict):
        return None

    return cast("dict[str, object]", servers)


def _registry_mcp_signal(
    servers: dict[str, object],
    registry: dict[str, tuple[Path, dict[str, Any]]],
) -> ConfigSignal:
    """Classify deployed MCP entries against the rendered registry definitions."""
    for name, (_path, expected_config) in registry.items():
        if name not in servers or servers[name] != expected_config:
            return ConfigSignal.REGISTRY_DRIFT

    if set(servers.keys()) - set(registry.keys()):
        return ConfigSignal.USER_MCP
    return ConfigSignal.OK


def collect_mcp_config_state(target: Path) -> ConfigSignal:
    """Assess the state of the ``.mcp.json`` MCP configuration.

    Args:
        target: Workspace root directory.

    Returns:
        :class:`~vaultspec_core.core.diagnosis.signals.ConfigSignal`
        reflecting the observed MCP configuration state.
    """
    servers = read_mcp_servers(target / ".mcp.json")
    if servers is None:
        return ConfigSignal.PARTIAL_MCP

    # Check registry drift: compare deployed entries against definitions
    # rendered for the workspace's resolved mode. The seeded builtin carries
    # mode-neutral placeholder tokens, so an unrendered registry entry can never
    # equal the rendered .mcp.json launch and would report drift on every
    # workspace. resolve_render_mode's legacy-absent rule keeps a pre-install-mode
    # workspace on the dependency-shaped expectation.
    from ..mcps import collect_mcp_servers
    from ..workspace_mode import resolve_render_mode

    registry = collect_mcp_servers(mode=resolve_render_mode(target), target=target)
    if registry:
        return _registry_mcp_signal(servers, registry)

    # Fallback when no registry is available (pre-registry workspace)
    if "vaultspec-core" not in servers:
        return ConfigSignal.PARTIAL_MCP

    if len(servers) > 1:
        return ConfigSignal.USER_MCP

    return ConfigSignal.OK


def collect_vault_content_state(target: Path) -> tuple[VaultContentSignal, int, int]:
    """Assess generated template annotations in ``.vault/`` without mutating.

    This collector intentionally avoids the vault scanner because scanner access
    can trigger lazy migrations. Doctor must remain a read-only signal surface.

    Args:
        target: Workspace root directory.

    Returns:
        ``(signal, annotated_document_count, unreadable_markdown_count)``.
    """
    from ...config import get_config
    from ...vaultcore.checks.annotations import strip_template_annotations

    vault_dir = target / get_config().docs_dir
    if not vault_dir.is_dir():
        return VaultContentSignal.NO_VAULT, 0, 0

    annotated = 0
    unreadable = 0
    for path in sorted(vault_dir.rglob("*.md")):
        if ".obsidian" in path.parts or "_archive" in path.parts:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            unreadable += 1
            continue

        _cleaned, stats = strip_template_annotations(content)
        if stats.total:
            annotated += 1

    if annotated:
        return VaultContentSignal.ANNOTATIONS, annotated, unreadable
    if unreadable:
        return VaultContentSignal.UNREADABLE, annotated, unreadable
    return VaultContentSignal.CLEAN, annotated, unreadable


def collect_gitignore_state(target: Path) -> GitignoreSignal:
    """Assess the state of vaultspec-managed ``.gitignore`` entries.

    Args:
        target: Workspace root directory.

    Returns:
        :class:`~vaultspec_core.core.diagnosis.signals.GitignoreSignal`
        reflecting the observed state.
    """
    from ..gitignore import find_markers, get_recommended_entries

    gi_path = target / ".gitignore"
    if not gi_path.exists():
        return GitignoreSignal.NO_FILE

    try:
        content = gi_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Cannot read .gitignore %s: %s", gi_path, exc)
        return GitignoreSignal.NO_FILE

    lines = [line.strip() for line in content.splitlines()]
    begins, ends = find_markers(lines)

    if not begins and not ends:
        return GitignoreSignal.NO_ENTRIES

    # Any state that isn't exactly one BEGIN before exactly one END is corrupted.
    if len(begins) != 1 or len(ends) != 1 or begins[0] >= ends[0]:
        return GitignoreSignal.CORRUPTED

    begin_idx = begins[0]
    end_idx = ends[0]
    block_entries = [
        line.rstrip() for line in lines[begin_idx + 1 : end_idx] if line.strip()
    ]

    # Contradictory check: is an entry in the block explicitly unignored elsewhere?
    # (i.e. starts with "!")
    unignored = {line[1:].strip() for line in lines if line.startswith("!")}
    for entry in block_entries:
        if entry in unignored or entry.rstrip("/") in unignored:
            return GitignoreSignal.CORRUPTED

    # The managed block lists only runtime by-products; authored content
    # is team-shared (cli-spec-gitignore ADR). The recommended set no
    # longer varies by source-repo mode, so the diagnosis compares against
    # one canonical shape.
    recommended = get_recommended_entries(target)

    # Check if all recommended entries are present in the block.
    # We allow extra entries (idempotency is handled by ensure_gitignore_block).
    complete = all(entry in block_entries for entry in recommended)
    return GitignoreSignal.COMPLETE if complete else GitignoreSignal.PARTIAL


def collect_gitattributes_state(target: Path) -> GitattributesSignal:
    """Assess the state of vaultspec-managed ``.gitattributes`` entries.

    Args:
        target: Workspace root directory.

    Returns:
        :class:`~vaultspec_core.core.diagnosis.signals.GitattributesSignal`
        reflecting the observed state.
    """
    from ..gitattributes import DEFAULT_ENTRIES, find_markers, has_valid_block

    ga_path = target / ".gitattributes"
    if not ga_path.exists():
        return GitattributesSignal.NO_FILE

    try:
        content = ga_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Cannot read .gitattributes %s: %s", ga_path, exc)
        return GitattributesSignal.NO_FILE

    lines = [line.strip() for line in content.splitlines()]
    begins, ends = find_markers(lines)

    if not begins and not ends:
        return GitattributesSignal.NO_ENTRIES

    if not has_valid_block(lines):
        return GitattributesSignal.CORRUPTED

    begin_idx = begins[0]
    end_idx = ends[0]
    block_entries = [
        line.rstrip() for line in lines[begin_idx + 1 : end_idx] if line.strip()
    ]

    if all(entry in block_entries for entry in DEFAULT_ENTRIES):
        return GitattributesSignal.COMPLETE

    return GitattributesSignal.PARTIAL
