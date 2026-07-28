"""Resolve selected providers to their native MCP configuration targets.

Split out of :mod:`vaultspec_core.core.mcps`. See that module's docstring for
the ownership-fingerprint convergence story this package implements.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

from . import types as _t
from .enums import McpScope, McpTargetFormat, ProviderCapability, Tool
from .exceptions import VaultSpecError
from .types import McpTarget


def _coerce_scope(scope: McpScope | str) -> McpScope:
    try:
        return scope if isinstance(scope, McpScope) else McpScope(scope)
    except ValueError as exc:
        choices = ", ".join(item.value for item in McpScope)
        raise VaultSpecError(
            f"Unsupported MCP scope: {scope}",
            hint=f"Choose one of: {choices}.",
        ) from exc


def _selected_mcp_tools(
    provider: Tool | str,
    *,
    enrolled: Iterable[Tool] | None,
) -> tuple[Tool, ...]:
    """Return selected MCP-capable providers in canonical tool order."""
    ctx = _t.get_context()
    if enrolled is None:
        from .manifest import installed_tool_configs

        available = installed_tool_configs()
    else:
        selected = set(enrolled)
        available = {
            tool: cfg for tool, cfg in ctx.tool_configs.items() if tool in selected
        }

    if provider == "all":
        candidates = tuple(tool for tool in Tool if tool in available)
    else:
        try:
            selected_tool = provider if isinstance(provider, Tool) else Tool(provider)
        except ValueError as exc:
            raise VaultSpecError(f"Unsupported MCP provider: {provider}") from exc
        if selected_tool not in available:
            raise VaultSpecError(
                f"MCP provider '{selected_tool.value}' is not enrolled.",
                hint="Install the provider or pass the freshly selected provider set.",
            )
        candidates = (selected_tool,)

    supported: list[Tool] = []
    for tool in candidates:
        cfg = available[tool]
        if ProviderCapability.MCPS in cfg.capabilities:
            supported.append(tool)
        elif provider != "all":
            raise VaultSpecError(
                f"Provider '{tool.value}' has no verified MCP target contract."
            )
    return tuple(supported)


def _claude_user_config_path() -> Path:
    """Return Claude Code's user/local MCP store."""
    return Path.home() / ".claude.json"


def _codex_user_config_path() -> Path:
    """Return Codex's user MCP store, honoring ``CODEX_HOME``."""
    configured = os.environ.get("CODEX_HOME")
    home = Path(configured).expanduser() if configured else Path.home() / ".codex"
    return home / "config.toml"


def resolve_mcp_targets(
    provider: Tool | str = "all",
    *,
    scope: McpScope | str = McpScope.PROJECT,
    target_dir: Path | None = None,
    enrolled: Iterable[Tool] | None = None,
) -> tuple[McpTarget, ...]:
    """Resolve selected providers to their native MCP configuration targets.

    ``enrolled`` is the fresh-install seam: callers can supply the provider set
    selected for the current install before the provider manifest is written.
    Ordinary callers omit it and resolution uses the committed manifest.
    """
    try:
        ctx = _t.get_context()
    except LookupError:
        if target_dir is None:
            raise VaultSpecError(
                "No workspace context or explicit MCP target directory is available."
            ) from None
        ctx = _t.init_paths(target_dir)
    root = target_dir or ctx.target_dir
    if ctx.target_dir.resolve() != root.resolve():
        ctx = _t.init_paths(root)
    resolved_scope = _coerce_scope(scope)
    tools = _selected_mcp_tools(provider, enrolled=enrolled)
    targets: list[McpTarget] = []

    for tool in tools:
        cfg = ctx.tool_configs[tool]
        if tool is Tool.CLAUDE:
            path = (
                root / ".mcp.json"
                if resolved_scope is McpScope.PROJECT
                else _claude_user_config_path()
            )
            target_format = McpTargetFormat.JSON
        elif tool is Tool.CODEX:
            if resolved_scope is McpScope.LOCAL:
                raise VaultSpecError(
                    "Codex does not define a distinct local MCP scope.",
                    hint="Use project scope or explicitly request user scope.",
                )
            path = (
                root / ".codex" / "config.toml"
                if resolved_scope is McpScope.PROJECT
                else _codex_user_config_path()
            )
            target_format = McpTargetFormat.TOML
        elif tool is Tool.ANTIGRAVITY:
            if resolved_scope is not McpScope.PROJECT:
                raise VaultSpecError(
                    "Antigravity MCP enrollment currently supports project scope only."
                )
            if cfg.mcp_config_file is None:
                raise VaultSpecError("Antigravity MCP target is not configured.")
            path = cfg.mcp_config_file
            target_format = McpTargetFormat.JSON
        else:
            raise VaultSpecError(
                f"Provider '{tool.value}' has no native MCP target resolver."
            )
        targets.append(
            McpTarget(
                provider=tool,
                scope=resolved_scope,
                path=path,
                format=target_format,
            )
        )
    return tuple(targets)
