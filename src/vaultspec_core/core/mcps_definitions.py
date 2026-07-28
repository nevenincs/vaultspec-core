"""Collect, list, scaffold, and report on canonical MCP definitions.

Split out of :mod:`vaultspec_core.core.mcps`. See that module's docstring for
the ownership-fingerprint convergence story this package implements.
"""

from __future__ import annotations

import json
import logging
import tomllib
from collections.abc import Iterable
from pathlib import Path
from typing import Any, cast

from . import types as _t
from .enums import InstallMode, McpScope, McpTargetFormat, Tool
from .exceptions import ResourceExistsError, ResourceNotFoundError, VaultSpecError
from .helpers import atomic_write, ensure_dir
from .mcps_mode import _render_definition_for_sync
from .mcps_native import (
    _LEGACY_MANAGED_KEY,
    _TOML_BLOCK_TYPE,
    _json_server_map,
    _managed_toml_content,
    _normalized_sources,
    _toml_servers,
)
from .mcps_ownership import (
    _owned_names,
    _ownership_path,
    _OwnershipState,
    _read_ownership,
)
from .mcps_targets import _coerce_scope, resolve_mcp_targets
from .tags import TagError, strip_block
from .types import McpTarget, SyncResult

logger = logging.getLogger(__name__)

#: Re-exported (with underscore intact) for :mod:`vaultspec_core.core.mcps`
#: and :mod:`vaultspec_core.core.mcps_sync`, which reach into these as the
#: single public import surface for MCP definitions.
__all__ = ["_get_mcps_src_dir", "_server_name"]


def _server_name(filename: str) -> str:
    """Derive the MCP server name from a definition filename.

    Strips ``.builtin.json`` as a unit first, then falls back to ``.json``.

    Args:
        filename: The definition filename (e.g. ``vaultspec-core.builtin.json``).

    Returns:
        The server name (e.g. ``vaultspec-core``).
    """
    if filename.endswith(".builtin.json"):
        return filename[: -len(".builtin.json")]
    if filename.endswith(".json"):
        return filename[: -len(".json")]
    return filename


def _validate_server_name(name: str) -> None:
    """Raise :class:`VaultSpecError` if *name* is unsafe for use as a filename.

    Guards against path traversal, empty names, reserved suffixes, and
    OS-unsafe characters.
    """
    if not name or not name.strip():
        raise VaultSpecError("MCP server name must not be empty.")
    if "/" in name or "\\" in name or ".." in name:
        raise VaultSpecError(f"Invalid MCP server name: {name}")
    if name.endswith(".builtin.json") or name.endswith(".builtin"):
        raise VaultSpecError(
            "Cannot use '.builtin' suffix (reserved for package-bundled definitions)."
        )


def _get_mcps_src_dir() -> Path | None:
    """Return the MCP source directory from the active context, or ``None``."""
    try:
        return _t.get_context().mcps_src_dir
    except LookupError:
        return None


def collect_mcp_servers(
    warnings: list[str] | None = None,
    mode: InstallMode | None = None,
    target: Path | None = None,
) -> dict[str, tuple[Path, dict[str, Any]]]:
    """Collect MCP server definitions from ``.vaultspec/mcps/``.

    Reads and parses every ``.json`` file in the MCP source directory,
    returning a mapping of server name to (source path, parsed config).

    When *mode* is supplied, each parsed definition is rendered before being
    returned, so the mode-neutral placeholder tokens in a builtin definition
    become a concrete launch command. Rendering is *per definition*, not
    sync-wide: a definition that names its own declaring package renders at that
    package's committed render mode, while a definition without that metadata -
    core's own builtin - renders at *mode*. This keeps a mixed-mode workspace
    (core as a dependency, a companion package as a tool) stable, since each
    managed entry is written in its own declared shape rather than flattened
    onto whichever single mode the caller resolved for core. See
    :func:`~vaultspec_core.core.mcps_mode._render_definition_for_sync` for the
    resolution rule. The merge pipeline that feeds
    :func:`~vaultspec_core.core.mcps_sync.mcp_sync` therefore writes the
    correctly-shaped form for every entry into each provider-native target.
    When *mode* is ``None`` the raw (token-carrying) definitions are returned
    unchanged - the correct behaviour for callers that only inspect server
    *names* (uninstall, source counts) rather than the launch command.

    Args:
        warnings: Optional list to append parse-error messages to.
        mode: Provisioning mode to render *core's own* definition for, and the
            fallback for any definition whose per-package mode cannot be
            resolved, or ``None`` to return the raw parsed definitions.
        target: Workspace root directory used to resolve each definition's own
            declaring-package render mode when *mode* is supplied. ``None``
            skips the per-package lookup, so every definition renders at *mode*.

    Returns:
        Mapping of server name to ``(source_path, config_dict)``.
    """
    mcps_dir = _get_mcps_src_dir()
    if mcps_dir is None or not mcps_dir.exists():
        return {}

    sources: dict[str, tuple[Path, dict[str, Any]]] = {}
    for f in sorted(mcps_dir.glob("*.json")):
        try:
            raw = json.loads(f.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                msg = f"MCP definition {f.name} is not a JSON object"
                logger.error(msg)
                if warnings is not None:
                    warnings.append(msg)
                continue
            payload = cast("dict[str, Any]", raw)
            name = _server_name(f.name)
            if not name:
                continue
            if mode is not None:
                payload = _render_definition_for_sync(payload, mode, target)
            sources[name] = (f, payload)
        except (json.JSONDecodeError, OSError) as e:
            msg = f"Failed to read/parse MCP definition {f}: {e}"
            logger.error(msg)
            if warnings is not None:
                warnings.append(msg)
    return sources


def mcp_list() -> list[dict[str, str]]:
    """Return a list of MCP server metadata dicts.

    Each dict contains ``"name"`` and ``"source"`` (``"Built-in"`` or
    ``"Custom"``).
    """
    mcps_dir = _get_mcps_src_dir()
    if mcps_dir is None or not mcps_dir.exists():
        return []

    items: dict[str, dict[str, str]] = {}
    for f in sorted(mcps_dir.glob("*.json")):
        name = _server_name(f.name)
        if not name:
            continue
        is_builtin = f.name.endswith(".builtin.json")
        if name in items:
            if not is_builtin:
                items[name]["source"] = "Custom (shadows Built-in)"
        else:
            items[name] = {
                "name": name,
                "source": "Built-in" if is_builtin else "Custom",
            }
    return list(items.values())


def _empty_mcp_status(
    status: str,
    warnings: list[str],
    definitions: list[str] | None = None,
) -> dict[str, Any]:
    """Build the shared empty-result shape for the early-exit branches of `mcp_status`.

    Args:
        status: The aggregate status value to report.
        warnings: Warning messages accumulated so far.
        definitions: Known definition names, when any were already collected.
            ``missing`` mirrors ``definitions`` since no provider was assessed.

    Returns:
        A fully-shaped (but empty) `mcp_status` payload.
    """
    definitions = definitions or []
    return {
        "status": status,
        "config_path": None,
        "config_exists": False,
        "definitions": definitions,
        "configured": [],
        "managed": [],
        "missing": definitions,
        "drifted": [],
        "stale_managed": [],
        "external": [],
        "providers": {},
        "warnings": warnings,
    }


def _read_target_native_state(
    target: McpTarget, root: Path
) -> tuple[dict[str, dict[str, Any]], set[str], str | None]:
    """Parse *target*'s native config file into servers and managed names.

    Args:
        target: The resolved MCP target (config path, format, provider, scope).
        root: Workspace root used to resolve provider-native server maps.

    Returns:
        A ``(servers, managed_names, error_warning)`` tuple. *servers* and
        *managed_names* are empty when the target's config file does not
        exist; *error_warning* is set (and *servers*/*managed_names* reflect
        whatever was parsed before the failure) when the file exists but
        cannot be parsed.
    """
    servers: dict[str, dict[str, Any]] = {}
    managed: set[str] = set()
    if not target.path.exists():
        return servers, managed, None
    try:
        if target.format is McpTargetFormat.JSON:
            raw = json.loads(target.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise VaultSpecError("JSON root is not an object.")
            payload = cast("dict[str, Any]", raw)
            native = _json_server_map(payload, target, root)
            servers = {
                str(name): dict(cast("dict[str, Any]", config))
                for name, config in native.items()
                if isinstance(config, dict)
            }
            legacy = payload.get(_LEGACY_MANAGED_KEY, [])
            if isinstance(legacy, list):
                legacy_items = cast("list[Any]", legacy)
                managed.update(name for name in legacy_items if isinstance(name, str))
        else:
            content = target.path.read_text(encoding="utf-8")
            outside = _toml_servers(strip_block(content, _TOML_BLOCK_TYPE))
            block = _toml_servers(_managed_toml_content(content))
            servers = {**outside, **block}
            managed.update(block)
    except (
        json.JSONDecodeError,
        OSError,
        TagError,
        tomllib.TOMLDecodeError,
        VaultSpecError,
    ) as exc:
        return servers, managed, f"Cannot parse {target.path}: {exc}"
    return servers, managed, None


def _resolve_provider_status(
    invalid: bool,
    config_exists: bool,
    has_definitions: bool,
    missing: list[str],
    drifted: list[str],
    stale: list[str],
) -> str:
    """Classify a single provider's enrollment health.

    Args:
        invalid: Whether the target's config file failed to parse.
        config_exists: Whether the target's config file exists on disk.
        has_definitions: Whether any MCP definitions were collected at all.
        missing: Definition names absent from the provider's config.
        drifted: Managed entries whose written config no longer matches source.
        stale: Managed entries with no matching definition.

    Returns:
        One of ``invalid_config``, ``missing_config``, ``no_definitions``,
        ``partial``, or ``ok``.
    """
    if invalid:
        return "invalid_config"
    if not config_exists:
        return "missing_config" if has_definitions else "no_definitions"
    if missing or drifted or stale:
        return "partial"
    return "ok"


def _evaluate_provider_target(
    target: McpTarget,
    sources: dict[str, tuple[Path, dict[str, Any]]],
    definitions: list[str],
    root: Path,
    state: _OwnershipState,
) -> dict[str, Any]:
    """Assess one resolved MCP target's enrollment health.

    Args:
        target: The resolved MCP target (config path, format, provider, scope).
        sources: Collected MCP definitions, as returned by `collect_mcp_servers`.
        definitions: Sorted names of every collected definition.
        root: Workspace root used to normalize sources against *target*.
        state: Parsed ownership state for the target's scope.

    Returns:
        The per-provider status dict, as embedded under ``providers`` in the
        `mcp_status` payload.
    """
    normalization = SyncResult()
    target_sources = _normalized_sources(sources, target, normalization)
    managed = _owned_names(state, target)
    target_warnings = list(normalization.warnings)

    servers, native_managed, parse_warning = _read_target_native_state(target, root)
    managed.update(native_managed)
    if parse_warning is not None:
        target_warnings.append(parse_warning)
    managed.intersection_update(servers)

    configured = sorted(servers)
    missing = sorted(set(definitions) - set(servers))
    drifted = sorted(
        name
        for name in managed & set(target_sources)
        if servers[name] != target_sources[name][1]
    )
    stale = sorted(managed - set(definitions))
    external = sorted(set(servers) - managed)
    target_status = _resolve_provider_status(
        invalid=parse_warning is not None,
        config_exists=target.path.exists(),
        has_definitions=bool(definitions),
        missing=missing,
        drifted=drifted,
        stale=stale,
    )
    return {
        "status": target_status,
        "scope": target.scope.value,
        "config_path": str(target.path),
        "config_exists": target.path.exists(),
        "configured": configured,
        "managed": sorted(managed),
        "missing": missing,
        "drifted": drifted,
        "stale_managed": stale,
        "external": external,
        "warnings": target_warnings,
    }


def _aggregate_provider_statuses(providers: dict[str, dict[str, Any]]) -> str:
    """Roll up per-provider statuses into a single aggregate status.

    Args:
        providers: The per-provider status dicts assessed for this call.

    Returns:
        ``no_providers`` when *providers* is empty, ``invalid_config`` if any
        provider failed to parse, ``ok`` when every provider is healthy (or
        has no definitions to enroll), otherwise ``partial``.
    """
    statuses = {data["status"] for data in providers.values()}
    if not statuses:
        return "no_providers"
    if "invalid_config" in statuses:
        return "invalid_config"
    if statuses <= {"ok", "no_definitions"}:
        return "ok"
    return "partial"


def mcp_status(
    *,
    provider: Tool | str = "all",
    scope: McpScope | str = McpScope.PROJECT,
    target_dir: Path | None = None,
    enrolled: Iterable[Tool] | None = None,
) -> dict[str, Any]:
    """Return aggregate and per-provider enrollment health.

    Status reports configuration and ownership state only; it does not start or
    probe an MCP server.
    """
    try:
        root = target_dir or _t.get_context().target_dir
    except LookupError:
        return _empty_mcp_status(
            "no_context", ["No workspace context available for MCP status."]
        )

    from .workspace_mode import CORE_DISTRIBUTION_NAME, resolve_render_mode

    try:
        resolved_scope = _coerce_scope(scope)
        targets = resolve_mcp_targets(
            provider,
            scope=resolved_scope,
            target_dir=root,
            enrolled=enrolled,
        )
    except VaultSpecError as exc:
        return _empty_mcp_status("invalid_target", [str(exc)])

    render_mode = resolve_render_mode(root, package=CORE_DISTRIBUTION_NAME)
    parse_warnings: list[str] = []
    sources = collect_mcp_servers(
        warnings=parse_warnings, mode=render_mode, target=root
    )
    definitions = sorted(sources)

    warnings = list(parse_warnings)
    try:
        state = _read_ownership(_ownership_path(root, resolved_scope))
    except VaultSpecError as exc:
        return _empty_mcp_status(
            "invalid_target", [*warnings, str(exc)], definitions=definitions
        )

    providers: dict[str, dict[str, Any]] = {}
    for target in targets:
        provider_data = _evaluate_provider_target(
            target, sources, definitions, root, state
        )
        providers[target.provider.value] = provider_data
        warnings.extend(provider_data["warnings"])

    def aggregate(key: str) -> list[str]:
        return sorted({item for data in providers.values() for item in data[key]})

    return {
        "status": _aggregate_provider_statuses(providers),
        "config_path": (
            next(iter(providers.values()))["config_path"]
            if len(providers) == 1
            else None
        ),
        "config_exists": bool(providers)
        and all(data["config_exists"] for data in providers.values()),
        "definitions": definitions,
        "configured": aggregate("configured"),
        "managed": aggregate("managed"),
        "missing": aggregate("missing"),
        "drifted": aggregate("drifted"),
        "stale_managed": aggregate("stale_managed"),
        "external": aggregate("external"),
        "providers": providers,
        "warnings": warnings,
    }


def mcp_add(
    name: str,
    config: object | None = None,
    force: bool = False,
) -> Path:
    """Scaffold a new custom MCP server definition.

    Args:
        name: Server name.
        config: Server configuration dict, typically decoded from a JSON
            string at the CLI boundary and so genuinely untyped until the
            ``isinstance`` check below confirms its shape. Uses an empty
            scaffold when ``None``.
        force: Whether to overwrite an existing definition.

    Returns:
        Path to the created definition file.

    Raises:
        ResourceExistsError: If the definition exists and *force* is ``False``.
    """
    mcps_dir = _get_mcps_src_dir()
    if mcps_dir is None:
        raise ResourceNotFoundError(
            "MCP source directory not configured.",
            hint="Run 'vaultspec-core install' first.",
        )
    ensure_dir(mcps_dir)

    _validate_server_name(name)

    if config is not None and not isinstance(config, dict):
        raise VaultSpecError("MCP configuration must be a JSON object (dict).")

    file_name = name if name.endswith(".json") else f"{name}.json"
    file_path = mcps_dir / file_name

    if file_path.exists() and not force:
        raise ResourceExistsError(
            f"MCP definition '{file_name}' exists. Use --force to overwrite."
        )

    server_config: dict[str, Any] = (
        cast("dict[str, Any]", config)
        if config is not None
        else {"command": "", "args": []}
    )
    atomic_write(file_path, json.dumps(server_config, indent=2) + "\n")
    logger.info("Created MCP definition: %s", file_path)
    return file_path


def mcp_remove(name: str) -> Path:
    """Delete an MCP server definition.

    Searches for ``{name}.json`` first (custom), then ``{name}.builtin.json``.
    This prioritizes removing custom overrides so users can revert to the
    built-in definition.

    Args:
        name: Server name.

    Returns:
        Path to the removed definition file.

    Raises:
        ResourceNotFoundError: If no definition file matches *name*.
    """
    _validate_server_name(name)

    mcps_dir = _get_mcps_src_dir()
    if mcps_dir is None or not mcps_dir.exists():
        raise ResourceNotFoundError(
            f"MCP definition '{name}' not found.",
            hint="No MCP definitions directory exists.",
        )

    for suffix in (".json", ".builtin.json"):
        candidate = mcps_dir / f"{name}{suffix}"
        if candidate.exists():
            candidate.unlink()
            logger.info("Removed MCP definition: %s", candidate)
            return candidate

    raise ResourceNotFoundError(f"MCP definition '{name}' not found.")
