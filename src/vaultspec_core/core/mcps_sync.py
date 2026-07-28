"""Reconcile canonical MCP definitions into provider-native host configuration.

Split out of :mod:`vaultspec_core.core.mcps`. See that module's docstring for
the ownership-fingerprint convergence story this package implements.
"""

from __future__ import annotations

import json
import logging
import tomllib
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from . import types as _t
from .enums import InstallMode, McpScope, McpTargetFormat, Tool
from .exceptions import VaultSpecError
from .helpers import atomic_write, ensure_dir
from .mcps_definitions import _get_mcps_src_dir, _server_name, collect_mcp_servers
from .mcps_native import (
    _LEGACY_MANAGED_KEY,
    _TOML_BLOCK_TYPE,
    _json_server_map,
    _managed_toml_content,
    _normalized_sources,
    _render_codex_servers,
    _strip_external_codex_server,
    _toml_servers,
    _write_json_target,
)
from .mcps_ownership import (
    _fingerprint,
    _launch_repr,
    _owned_fingerprints,
    _owned_names,
    _ownership_path,
    _read_ownership,
    _set_owned_names,
    _target_lock,
    _write_ownership,
)
from .mcps_targets import _coerce_scope, resolve_mcp_targets
from .tags import TagError, strip_block, upsert_block
from .types import McpTarget, SyncResult

logger = logging.getLogger(__name__)


def _existing_source_server_names() -> set[str]:
    """Return server names whose source file physically exists on disk.

    Unlike :func:`~vaultspec_core.core.mcps_definitions.collect_mcp_servers`,
    this never opens or parses the JSON files — a definition that exists but
    currently fails to parse (e.g. transient typo) is still reported as
    present. This is the correct signal for the prune step in
    :func:`mcp_sync`: a server must only be considered for orphan removal when
    its source file is *definitively absent*, not when parsing happened to
    fail this run. Otherwise a single typo in a managed definition would
    silently delete the corresponding provider-native enrollment on the next
    ``sync --force``, which is destructive and hard to recover from.
    """
    mcps_dir = _get_mcps_src_dir()
    if mcps_dir is None or not mcps_dir.exists():
        return set()
    names: set[str] = set()
    for f in mcps_dir.glob("*.json"):
        name = _server_name(f.name)
        if name:
            names.add(name)
    return names


def _apply_server_merge(
    servers: dict[str, dict[str, Any]],
    managed: set[str],
    external: set[str],
    sources: dict[str, tuple[Path, dict[str, Any]]],
    *,
    force: bool,
    prune: bool,
    result: SyncResult,
    label: str,
    force_managed: frozenset[str],
    recorded_fingerprints: dict[str, str],
) -> bool:
    """Apply ownership-safe desired state to one provider's normalized servers."""
    changed = False
    for name, (_path, config) in sources.items():
        if name not in servers:
            servers[name] = config
            managed.add(name)
            result.added += 1
            result.items.append((name, "[ADD]"))
            changed = True
        elif name in managed:
            if servers[name] == config:
                result.unchanged += 1
                result.items.append((name, "[UNCHANGED]"))
            elif force or name in force_managed:
                servers[name] = config
                result.updated += 1
                result.items.append((name, "[UPDATE]"))
                changed = True
            elif recorded_fingerprints.get(name) == _fingerprint(servers[name]):
                # Bytes still match what vaultspec last wrote, so the drift is
                # provably ours to converge, not a hand edit: refresh in place.
                old_launch = _launch_repr(servers[name])
                new_launch = _launch_repr(config)
                servers[name] = config
                result.updated += 1
                result.items.append((name, "[REFRESH]"))
                changed = True
                result.warnings.append(
                    f"MCP server '{name}' launch refreshed to the current "
                    f"standard: '{old_launch}' -> '{new_launch}' (managed "
                    "entry was unchanged since vaultspec wrote it; "
                    "hand-edited entries are never refreshed automatically)."
                )
            elif name in recorded_fingerprints:
                result.skipped += 1
                result.items.append((name, "[SKIP]"))
                result.warnings.append(
                    f"MCP server '{name}' in {label} differs from its definition "
                    "(use --force to overwrite)."
                )
            else:
                result.skipped += 1
                result.items.append((name, "[SKIP]"))
                result.warnings.append(
                    f"MCP server '{name}' in {label} differs from its definition "
                    "and has no recorded fingerprint to verify against; use "
                    "--force to overwrite."
                )
        elif force:
            servers[name] = config
            external.discard(name)
            managed.add(name)
            result.updated += 1
            result.items.append((name, "[ADOPT]"))
            changed = True
        else:
            result.skipped += 1
            result.items.append((name, "[SKIP]"))
            result.warnings.append(
                f"MCP server '{name}' in {label} is externally managed; "
                "use --force to adopt it explicitly."
            )

    if prune:
        on_disk = _existing_source_server_names()
        for name in sorted(managed - on_disk):
            if name in servers:
                servers.pop(name)
                result.pruned += 1
                result.items.append((name, "[DELETE]"))
                changed = True
            managed.discard(name)

    managed.intersection_update(servers)
    return changed


def _sync_json_target(
    target: McpTarget,
    root: Path,
    state: dict[str, Any],
    sources: dict[str, tuple[Path, dict[str, Any]]],
    *,
    dry_run: bool,
    force: bool,
    prune: bool,
    result: SyncResult,
    force_managed: frozenset[str],
) -> None:
    """Reconcile a Claude or Antigravity JSON target without host-only keys."""
    with _target_lock(target.path, dry_run=dry_run):
        raw: dict[str, Any] = {}
        if target.path.exists():
            try:
                loaded = json.loads(target.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                result.errors.append(f"Cannot parse {target.path}: {exc}")
                result.errored += 1
                return
            if not isinstance(loaded, dict):
                result.errors.append(f"MCP target {target.path} is not a JSON object.")
                result.errored += 1
                return
            raw = loaded

        try:
            untyped_servers = _json_server_map(raw, target, root)
        except VaultSpecError as exc:
            result.errors.append(str(exc))
            result.errored += 1
            return
        servers = {
            str(name): config
            for name, config in untyped_servers.items()
            if isinstance(config, dict)
        }
        if len(servers) != len(untyped_servers):
            result.errors.append(
                f"MCP target {target.path} contains a non-object server."
            )
            result.errored += 1
            return

        managed = _owned_names(state, target) & set(servers)
        recorded_fingerprints = _owned_fingerprints(state, target)
        legacy = raw.pop(_LEGACY_MANAGED_KEY, None)
        migrated = (
            {name for name in legacy if isinstance(name, str) and name in servers}
            if isinstance(legacy, list)
            else set()
        )
        if migrated:
            managed.update(migrated)
            result.warnings.append(
                f"Migrated affirmative legacy ownership for {sorted(migrated)} "
                f"from {target.path}."
            )
        external = set(servers) - managed
        changed = legacy is not None
        changed |= _apply_server_merge(
            servers,
            managed,
            external,
            sources,
            force=force,
            prune=prune,
            result=result,
            label=str(target.path),
            force_managed=force_managed,
            recorded_fingerprints=recorded_fingerprints,
        )
        untyped_servers.clear()
        untyped_servers.update(servers)
        _set_owned_names(
            state, target, {name: servers[name] for name in managed if name in servers}
        )
        if changed and not dry_run:
            _write_json_target(target.path, raw, target, root)


def _sync_toml_target(
    target: McpTarget,
    state: dict[str, Any],
    sources: dict[str, tuple[Path, dict[str, Any]]],
    *,
    dry_run: bool,
    force: bool,
    prune: bool,
    result: SyncResult,
    force_managed: frozenset[str],
) -> None:
    """Reconcile Codex tables inside one comment-bounded managed block."""
    with _target_lock(target.path, dry_run=dry_run):
        content = ""
        if target.path.exists():
            try:
                content = target.path.read_text(encoding="utf-8")
            except OSError as exc:
                result.errors.append(f"Cannot read {target.path}: {exc}")
                result.errored += 1
                return
        try:
            if content.strip():
                tomllib.loads(content)
            managed_content = _managed_toml_content(content)
            outside_content = strip_block(content, _TOML_BLOCK_TYPE)
            outside = _toml_servers(outside_content)
            block_servers = _toml_servers(managed_content)
        except (TagError, tomllib.TOMLDecodeError, VaultSpecError) as exc:
            result.errors.append(f"Cannot parse {target.path}: {exc}")
            result.errored += 1
            return

        if force:
            for name in sorted(set(sources) & set(outside)):
                stripped = _strip_external_codex_server(content, name)
                try:
                    remaining = _toml_servers(strip_block(stripped, _TOML_BLOCK_TYPE))
                except (TagError, tomllib.TOMLDecodeError, VaultSpecError) as exc:
                    result.errors.append(
                        f"Cannot adopt Codex MCP server '{name}' in "
                        f"{target.path}: {exc}"
                    )
                    result.errored += 1
                    return
                if name in remaining:
                    result.errors.append(
                        f"Cannot safely adopt Codex MCP server '{name}' in "
                        f"{target.path}; its external declaration is not a "
                        "removable table."
                    )
                    result.errored += 1
                    return
                content = stripped

        recorded = _owned_names(state, target)
        recorded_fingerprints = _owned_fingerprints(state, target)
        managed = (recorded | set(block_servers)) & set(block_servers)
        servers = {**outside, **block_servers}
        external = set(outside)
        changed = _apply_server_merge(
            servers,
            managed,
            external,
            sources,
            force=force,
            prune=prune,
            result=result,
            label=str(target.path),
            force_managed=force_managed,
            recorded_fingerprints=recorded_fingerprints,
        )
        new_managed = {
            name: servers[name]
            for name in managed
            if name in servers and name not in external
        }
        _set_owned_names(state, target, new_managed)
        if changed and not dry_run:
            rendered = _render_codex_servers(new_managed)
            updated = (
                upsert_block(content, _TOML_BLOCK_TYPE, rendered, comment_prefix="# ")
                if rendered
                else strip_block(content, _TOML_BLOCK_TYPE)
            )
            ensure_dir(target.path.parent)
            if updated:
                atomic_write(target.path, updated)
            elif target.path.exists():
                target.path.unlink()


def mcp_sync(
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
    """Reconcile canonical MCP definitions into selected native host targets.

    Project scope is the safe default. User and Claude-local stores are touched
    only when the caller explicitly selects those scopes. Ownership is stored
    outside host schemas, and Codex content is bounded by a comment-only TOML
    block so unrelated settings and comments remain byte-stable.

    Args:
        dry_run: If ``True``, compute changes without writing.
        force: Overwrite entries that differ from their definitions.
        prune: If ``True``, remove managed entries whose source files have
            been deleted. Mirrors ``rules_sync``/``agents_sync``.
        mode: Provisioning mode to render definitions for, or ``None`` to
            resolve it from the committed workspace declaration.
        force_managed: Already-owned entries eligible for surgical updates.
        provider: One provider name/member, or ``"all"`` enrolled providers.
        scope: Explicit native host scope; defaults to project.
        target_dir: Workspace root override used by companion packages.
        enrolled: Fresh-install provider selection before manifest persistence.

    Returns:
        :class:`~vaultspec_core.core.types.SyncResult` with sync statistics.
        Per-provider MCP-file results are recorded under ``per_tool``.
    """
    result = SyncResult()

    try:
        root = target_dir or _t.get_context().target_dir
    except LookupError:
        result.errors.append("No workspace context available for MCP sync.")
        return result

    try:
        resolved_scope = _coerce_scope(scope)
        targets = resolve_mcp_targets(
            provider, scope=resolved_scope, target_dir=root, enrolled=enrolled
        )
    except VaultSpecError as exc:
        result.errors.append(str(exc))
        result.errored += 1
        return result

    if mode is None:
        from .workspace_mode import CORE_DISTRIBUTION_NAME, resolve_render_mode

        mode = resolve_render_mode(root, package=CORE_DISTRIBUTION_NAME)

    parse_warnings: list[str] = []
    sources = collect_mcp_servers(warnings=parse_warnings, mode=mode, target=root)
    result.warnings.extend(parse_warnings)
    ownership_path = _ownership_path(root, resolved_scope)
    with _target_lock(ownership_path, dry_run=dry_run):
        try:
            state = _read_ownership(ownership_path)
        except VaultSpecError as exc:
            result.errors.append(str(exc))
            result.errored += 1
            return result
        before_state = json.dumps(state, sort_keys=True)
        for target in targets:
            sub = SyncResult()
            target_sources = _normalized_sources(sources, target, sub)
            if target.format is McpTargetFormat.JSON:
                _sync_json_target(
                    target,
                    root,
                    state,
                    target_sources,
                    dry_run=dry_run,
                    force=force,
                    prune=prune,
                    result=sub,
                    force_managed=force_managed,
                )
            else:
                _sync_toml_target(
                    target,
                    state,
                    target_sources,
                    dry_run=dry_run,
                    force=force,
                    prune=prune,
                    result=sub,
                    force_managed=force_managed,
                )
            result.merge(sub)
            result.per_tool[target.provider.value] = sub
        if not dry_run and json.dumps(state, sort_keys=True) != before_state:
            if state["targets"]:
                _write_ownership(ownership_path, state)
            elif ownership_path.exists():
                ownership_path.unlink()

    return result
