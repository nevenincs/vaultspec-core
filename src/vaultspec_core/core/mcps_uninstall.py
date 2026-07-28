"""Remove recorded vaultspec-owned MCP enrollment from native host targets.

Split out of :mod:`vaultspec_core.core.mcps`. See that module's docstring for
the ownership-fingerprint convergence story this package implements.
"""

from __future__ import annotations

import json
import tomllib
from collections.abc import Iterable
from pathlib import Path

from .enums import McpScope, McpTargetFormat, Tool
from .exceptions import VaultSpecError
from .helpers import atomic_write
from .mcps_native import (
    _LEGACY_MANAGED_KEY,
    _TOML_BLOCK_TYPE,
    _json_server_map,
    _managed_toml_content,
    _render_codex_servers,
    _toml_servers,
    _write_json_target,
)
from .mcps_ownership import (
    _discard_owned_names,
    _owned_names,
    _ownership_path,
    _read_ownership,
    _target_lock,
    _write_ownership,
)
from .mcps_targets import _coerce_scope, resolve_mcp_targets
from .tags import TagError, strip_block, upsert_block
from .types import McpTarget, SyncResult


def _uninstall_json_target(
    target: McpTarget,
    root: Path,
    requested: set[str],
    *,
    dry_run: bool,
    result: SyncResult,
) -> None:
    """Drop *requested* owned servers from a Claude or Antigravity JSON target."""
    raw = json.loads(target.path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise VaultSpecError("JSON root is not an object.")
    servers = _json_server_map(raw, target, root)
    present = requested & set(servers)
    result.pruned += len(present)
    result.items.extend((name, "[DELETE]") for name in sorted(present))
    if dry_run:
        return
    for name in present:
        servers.pop(name, None)
    raw.pop(_LEGACY_MANAGED_KEY, None)
    _write_json_target(target.path, raw, target, root)


def _uninstall_toml_target(
    target: McpTarget,
    requested: set[str],
    *,
    dry_run: bool,
    result: SyncResult,
) -> None:
    """Drop *requested* owned servers from a Codex TOML target."""
    content = target.path.read_text(encoding="utf-8")
    block_servers = _toml_servers(_managed_toml_content(content))
    present = requested & set(block_servers)
    result.pruned += len(present)
    result.items.extend((name, "[DELETE]") for name in sorted(present))
    if dry_run:
        return
    for name in present:
        block_servers.pop(name, None)
    rendered = _render_codex_servers(block_servers)
    updated = (
        upsert_block(content, _TOML_BLOCK_TYPE, rendered, comment_prefix="# ")
        if rendered
        else strip_block(content, _TOML_BLOCK_TYPE)
    )
    if updated:
        atomic_write(target.path, updated)
    else:
        target.path.unlink()


def mcp_uninstall(
    target_dir: Path,
    *,
    dry_run: bool = False,
    provider: Tool | str = "all",
    scope: McpScope | str = McpScope.PROJECT,
    enrolled: Iterable[Tool] | None = None,
    names: Iterable[str] | None = None,
) -> SyncResult:
    """Remove recorded Vaultspec-owned enrollment from selected native targets.

    When *names* is provided, only those owned server names are removed.
    External host entries and canonical MCP definitions remain unchanged.
    """
    result = SyncResult()
    selected_names = frozenset(names) if names is not None else None
    try:
        resolved_scope = _coerce_scope(scope)
        targets = resolve_mcp_targets(
            provider,
            scope=resolved_scope,
            target_dir=target_dir,
            enrolled=enrolled,
        )
    except VaultSpecError as exc:
        result.errors.append(str(exc))
        result.errored += 1
        return result
    ownership_path = _ownership_path(target_dir, resolved_scope)
    with _target_lock(ownership_path, dry_run=dry_run):
        try:
            state = _read_ownership(ownership_path)
        except VaultSpecError as exc:
            result.errors.append(str(exc))
            result.errored += 1
            return result
        for target in targets:
            sub = SyncResult()
            managed = _owned_names(state, target)
            requested = managed if selected_names is None else managed & selected_names
            if not requested or not target.path.exists():
                if not dry_run:
                    _discard_owned_names(state, target, requested)
                result.per_tool[target.provider.value] = sub
                continue
            succeeded = False
            with _target_lock(target.path, dry_run=dry_run):
                try:
                    if target.format is McpTargetFormat.JSON:
                        _uninstall_json_target(
                            target,
                            target_dir,
                            requested,
                            dry_run=dry_run,
                            result=sub,
                        )
                    else:
                        _uninstall_toml_target(
                            target,
                            requested,
                            dry_run=dry_run,
                            result=sub,
                        )
                    succeeded = True
                except (
                    json.JSONDecodeError,
                    OSError,
                    TagError,
                    tomllib.TOMLDecodeError,
                    VaultSpecError,
                ) as exc:
                    sub.errored += 1
                    sub.errors.append(
                        f"Cannot uninstall MCPs from {target.path}: {exc}"
                    )
            if not dry_run and succeeded:
                _discard_owned_names(state, target, requested)
            result.merge(sub)
            result.per_tool[target.provider.value] = sub
        if not dry_run:
            if state["targets"]:
                _write_ownership(ownership_path, state)
            elif ownership_path.exists():
                ownership_path.unlink()
    return result
