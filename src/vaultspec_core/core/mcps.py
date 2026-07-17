"""Manage canonical MCP definitions and provider-native enrollment.

Definitions in ``.vaultspec/mcps/*.json`` describe provider-neutral stdio
servers. This module renders those definitions for each MCP-capable provider,
reconciles project or explicit broader-scope targets, and records ownership
outside host configuration so unrelated entries remain untouched.

A managed entry that drifted from its rendered definition converges
automatically, without ``--force``, whenever its on-disk bytes still match
the fingerprint recorded at the last write: the drift is provably one the
entry never survived a hand edit through, so refreshing it cannot destroy
user content. An entry whose bytes no longer match its recorded fingerprint,
or whose ownership record predates fingerprinting, keeps the existing
skip-and-warn behavior and still requires ``--force``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import tomllib
from collections.abc import Iterable
from contextlib import nullcontext
from pathlib import Path
from typing import Any

from . import types as _t
from .enums import (
    InstallMode,
    McpScope,
    McpTargetFormat,
    ProviderCapability,
    Tool,
    render_mode,
)
from .exceptions import ResourceExistsError, ResourceNotFoundError, VaultSpecError
from .helpers import advisory_lock, atomic_write, ensure_dir
from .tags import TagError, find_blocks, strip_block, upsert_block
from .types import McpTarget, SyncResult

logger = logging.getLogger(__name__)

#: Sentinel tokens carried by the mode-neutral builtin MCP definition
#: (``builtins/mcps/vaultspec-core.builtin.json``). They are deliberately
#: shaped so they cannot collide with any real command name or argument value,
#: so :func:`render_mcp_definition_for_mode` can detect and substitute them
#: unambiguously. The seeded ``.vaultspec/mcps/`` copy carries these same bytes
#: (keeping the ``BuiltinVersionSignal`` snapshot hash stable); substitution
#: happens only here, downstream, and only the substituted concrete command is
#: ever written into provider-native host configuration.
_MODE_COMMAND_TOKEN = "@@VAULTSPEC_INSTALL_MODE_COMMAND@@"
_MODE_ARGS_TOKEN = "@@VAULTSPEC_INSTALL_MODE_ARGS@@"

#: Optional metadata keys a mode-neutral MCP definition may carry alongside the
#: sentinel tokens to name the distribution and runnable module its launch
#: renders for. Absent on core's own builtin - which defaults to core's package
#: and module below, keeping that file byte-identical - and present on a
#: companion package's builtin so core's single sentinel-substitution renderer
#: produces *that* package's ``uv run``/``uvx`` launch without a second renderer.
#: They are consumed and stripped during substitution, so they never reach
#: provider-native host configuration.
_MODE_PACKAGE_KEY = "_vaultspec_mode_package"
_MODE_MODULE_KEY = "_vaultspec_mode_module"
_MODE_TOOL_SPEC_KEY = "_vaultspec_mode_tool_spec"

#: The distribution and module core's own MCP server launches through. Used as
#: the substitution defaults when a definition omits the per-definition
#: package/module keys, so core's token-only builtin renders exactly as before.
_DEFAULT_MCP_PACKAGE = "vaultspec-core"
_DEFAULT_MCP_MODULE = "vaultspec_core.mcp_server.app"


def render_launch_for_mode(
    mode: InstallMode,
    package: str,
    module: str,
    tool_spec: str | None = None,
) -> tuple[str, list[str]]:
    """Return the concrete ``(command, args)`` launch a package+module renders to.

    The single launch comparator for the three-mode model, parameterized by the
    distribution *package* and the runnable *module* so any core-provisioned
    package renders its MCP server through one shared shape rather than a
    per-package table. This is the seam a companion package (for example
    ``vaultspec-rag``) substitutes through: its mode-neutral builtin names its
    own package and module, and this helper produces the right launch for it.

    :attr:`~vaultspec_core.core.enums.InstallMode.DEV` is collapsed onto
    :attr:`~vaultspec_core.core.enums.InstallMode.DEPENDENCY` through
    :func:`~vaultspec_core.core.enums.render_mode` before the shape is chosen, so
    the dev-scoped bookkeeping member never grows a third launch branch.

    Dependency-rendered mode launches the module through the governed project's
    own venv with the ``--no-sync`` guard (``uv run --no-sync python -m
    <module>``): a static execution that resolves the existing venv and never
    installs, syncs, or otherwise mutates it, failing honestly when the venv is
    stale or broken instead of self-repairing at connect time. Tool mode
    launches the same module through an ephemeral ``uvx --from <package>``
    invocation so the distribution never enters the governed project's
    dependency set.

    Args:
        mode: The provisioning mode whose launch to render.
        package: Distribution name used as the workspace-mode identity and as
            the default ``uvx --from`` tool-mode requirement.
        module: Fully-qualified module the MCP server runs as ``python -m``.
        tool_spec: Optional tool-mode distribution requirement, such as
            ``"vaultspec-rag[mcp]"``. It affects only ``uvx --from``; package
            remains the declaration and mode-resolution identity.

    Returns:
        The ``(command, args)`` pair for the rendered mode.
    """
    if render_mode(mode) is InstallMode.DEPENDENCY:
        return "uv", ["run", "--no-sync", "python", "-m", module]
    return "uvx", ["--from", tool_spec or package, "python", "-m", module]


#: Core's own concrete MCP-server launch per mode, derived from the generalized
#: :func:`render_launch_for_mode` so this convenience table and the renderer can
#: never drift. Dependency mode is a static, ``--no-sync``-guarded execution
#: that resolves the existing venv without mutating it; tool mode launches the
#: same module entry point through an ephemeral ``uvx`` invocation. Only the two
#: rendered shapes are keyed (``DEV`` collapses onto ``DEPENDENCY``), which is
#: what the observed-shape matcher and the mode-flip tests read.
_MODE_MCP_LAUNCH: dict[InstallMode, tuple[str, list[str]]] = {
    mode: render_launch_for_mode(mode, _DEFAULT_MCP_PACKAGE, _DEFAULT_MCP_MODULE)
    for mode in (InstallMode.DEPENDENCY, InstallMode.TOOL)
}


def render_mcp_definition_for_mode(
    definition: dict[str, Any], mode: InstallMode
) -> dict[str, Any]:
    """Return *definition* with its mode-neutral tokens substituted for *mode*.

    Substitution is surgical and token-guarded: the ``command`` field is
    rewritten only when it equals :data:`_MODE_COMMAND_TOKEN`, and the ``args``
    field only when it equals the single-element token list
    ``[_MODE_ARGS_TOKEN]``. A definition that carries neither token - a
    user-authored custom MCP server, or an already-rendered entry - passes
    through unchanged, so this is safe to apply to every collected definition
    regardless of origin.

    The launch is produced by the generalized
    :func:`render_launch_for_mode`, which routes *mode* through
    :func:`~vaultspec_core.core.enums.render_mode` so the dev-scoped
    :attr:`~vaultspec_core.core.enums.InstallMode.DEV` member renders
    byte-identically to :attr:`~vaultspec_core.core.enums.InstallMode.DEPENDENCY`
    rather than falling off a two-key table. The distribution and module the
    launch targets come from the definition's own
    :data:`_MODE_PACKAGE_KEY`/:data:`_MODE_MODULE_KEY` metadata, defaulting to
    core's package and module when absent. Those keys and the optional
    :data:`_MODE_TOOL_SPEC_KEY` are stripped during substitution so launch
    metadata never reaches provider-native host configuration.

    Args:
        definition: A parsed MCP server definition (``command``/``args`` map).
        mode: The provisioning mode whose concrete launch to substitute.

    Returns:
        A shallow copy of *definition* with the tokens replaced by the
        mode-specific launch command and args and the substitution-metadata keys
        removed. The input is not mutated.
    """
    rendered = dict(definition)
    package = str(rendered.pop(_MODE_PACKAGE_KEY, _DEFAULT_MCP_PACKAGE))
    module = str(rendered.pop(_MODE_MODULE_KEY, _DEFAULT_MCP_MODULE))
    raw_tool_spec = rendered.pop(_MODE_TOOL_SPEC_KEY, None)
    tool_spec = str(raw_tool_spec) if raw_tool_spec is not None else None
    has_command_token = rendered.get("command") == _MODE_COMMAND_TOKEN
    has_args_token = rendered.get("args") == [_MODE_ARGS_TOKEN]
    if not (has_command_token or has_args_token):
        return rendered
    command, args = render_launch_for_mode(mode, package, module, tool_spec)
    if has_command_token:
        rendered["command"] = command
    if has_args_token:
        rendered["args"] = list(args)
    return rendered


def _render_definition_for_sync(
    definition: dict[str, Any],
    sync_mode: InstallMode,
    target: Path | None,
) -> dict[str, Any]:
    """Render one collected definition at its own declaring package's mode.

    The seam that keeps a mixed-mode workspace stable. A definition that names
    its own declaring package through :data:`_MODE_PACKAGE_KEY` renders at *that*
    package's committed render mode
    (:func:`~vaultspec_core.core.workspace_mode.resolve_render_mode`), not the
    sync-wide *sync_mode*, so a workspace that provisioned core as a dependency
    and a companion package (for example ``vaultspec-rag``) as a tool syncs each
    managed entry at its own declared shape rather than flattening every entry
    onto whichever single mode the caller resolved for core. A definition
    without the key - core's own token-only builtin - renders at *sync_mode*,
    which stays the caller's fallback (a plain sync's core-resolved render mode)
    or explicit override (the fresh-``install``/upgrade mode-flip value core
    writes only after this render runs). When *target* is unavailable the
    per-package lookup is skipped and every definition falls back to *sync_mode*,
    preserving the pre-per-package behaviour for callers with no workspace
    context.

    Args:
        definition: A parsed MCP server definition, possibly carrying the
            mode-neutral tokens and the ``_vaultspec_mode_package`` metadata key.
        sync_mode: The sync-wide mode, used for core's own definition and as the
            fallback when a per-package lookup cannot run.
        target: Workspace root directory for the per-package render-mode lookup,
            or ``None`` to skip it.

    Returns:
        The mode-rendered definition (a copy; the input is not mutated).
    """
    package = definition.get(_MODE_PACKAGE_KEY)
    if package is not None and target is not None:
        from .workspace_mode import resolve_render_mode

        def_mode = resolve_render_mode(target, package=str(package))
    else:
        def_mode = sync_mode
    return render_mcp_definition_for_mode(definition, def_mode)


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


_OWNERSHIP_VERSION = 1
_OWNERSHIP_FILENAME = "mcp-ownership.json"


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


def _ownership_path(root: Path, scope: McpScope) -> Path:
    if scope in {McpScope.PROJECT, McpScope.LOCAL}:
        return root / ".vaultspec" / _OWNERSHIP_FILENAME
    return Path.home() / ".vaultspec" / _OWNERSHIP_FILENAME


def _ownership_target_key(target: McpTarget) -> str:
    base = f"{target.provider.value}:{target.scope.value}"
    if target.scope is McpScope.USER:
        return f"{base}:{target.path.resolve()}"
    return base


def _read_ownership(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": _OWNERSHIP_VERSION, "targets": {}}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise VaultSpecError(
            f"Cannot read MCP ownership state at {path}: {exc}",
            hint="Repair or remove the corrupt sidecar before reconciling MCPs.",
        ) from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("targets"), dict):
        raise VaultSpecError(
            f"Invalid MCP ownership state at {path}.",
            hint="Expected an object with a 'targets' object.",
        )
    version = raw.get("version")
    if version != _OWNERSHIP_VERSION:
        raise VaultSpecError(f"Unsupported MCP ownership version at {path}: {version}")
    return raw


def _write_ownership(path: Path, state: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    atomic_write(path, json.dumps(state, indent=2, sort_keys=True) + "\n")


def _target_lock(path: Path, *, dry_run: bool) -> Any:
    """Return a no-op context for previews and a real advisory lock for writes."""
    return nullcontext() if dry_run else advisory_lock(path)


def _existing_source_server_names() -> set[str]:
    """Return server names whose source file physically exists on disk.

    Unlike :func:`collect_mcp_servers`, this never opens or parses the
    JSON files — a definition that exists but currently fails to parse
    (e.g. transient typo) is still reported as present. This is the
    correct signal for the prune step in :func:`mcp_sync`: a server
    must only be considered for orphan removal when its source file
    is *definitively absent*, not when parsing happened to fail this
    run. Otherwise a single typo in a managed definition would
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
    :func:`_render_definition_for_sync` for the resolution rule. The merge
    pipeline that feeds :func:`mcp_sync` therefore writes the correctly-shaped
    form for every entry into each provider-native target. When *mode* is
    ``None`` the raw (token-carrying) definitions are returned unchanged - the
    correct behaviour for callers that only inspect server *names* (uninstall,
    source counts) rather than the launch command.

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
            name = _server_name(f.name)
            if not name:
                continue
            if mode is not None:
                raw = _render_definition_for_sync(raw, mode, target)
            sources[name] = (f, raw)
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
        return {
            "status": "no_context",
            "config_path": None,
            "config_exists": False,
            "definitions": [],
            "configured": [],
            "managed": [],
            "missing": [],
            "drifted": [],
            "stale_managed": [],
            "external": [],
            "providers": {},
            "warnings": ["No workspace context available for MCP status."],
        }

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
        return {
            "status": "invalid_target",
            "config_path": None,
            "config_exists": False,
            "definitions": [],
            "configured": [],
            "managed": [],
            "missing": [],
            "drifted": [],
            "stale_managed": [],
            "external": [],
            "providers": {},
            "warnings": [str(exc)],
        }

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
        return {
            "status": "invalid_target",
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
            "warnings": [*warnings, str(exc)],
        }

    providers: dict[str, dict[str, Any]] = {}
    for target in targets:
        normalization = SyncResult()
        target_sources = _normalized_sources(sources, target, normalization)
        servers: dict[str, dict[str, Any]] = {}
        managed = _owned_names(state, target)
        target_warnings = list(normalization.warnings)
        invalid = False
        if target.path.exists():
            try:
                if target.format is McpTargetFormat.JSON:
                    raw = json.loads(target.path.read_text(encoding="utf-8"))
                    if not isinstance(raw, dict):
                        raise VaultSpecError("JSON root is not an object.")
                    native = _json_server_map(raw, target, root)
                    servers = {
                        str(name): dict(config)
                        for name, config in native.items()
                        if isinstance(config, dict)
                    }
                    legacy = raw.get(_LEGACY_MANAGED_KEY, [])
                    if isinstance(legacy, list):
                        managed.update(name for name in legacy if isinstance(name, str))
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
                invalid = True
                target_warnings.append(f"Cannot parse {target.path}: {exc}")
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
        if invalid:
            target_status = "invalid_config"
        elif not target.path.exists():
            target_status = "missing_config" if definitions else "no_definitions"
        elif missing or drifted or stale:
            target_status = "partial"
        else:
            target_status = "ok"
        providers[target.provider.value] = {
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
        warnings.extend(target_warnings)

    def aggregate(key: str) -> list[str]:
        return sorted({item for data in providers.values() for item in data[key]})

    statuses = {data["status"] for data in providers.values()}
    if not statuses:
        status = "no_providers"
    elif statuses <= {"ok", "no_definitions"}:
        status = "ok"
    else:
        status = "partial"
    if "invalid_config" in statuses:
        status = "invalid_config"
    return {
        "status": status,
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
    config: dict[str, Any] | None = None,
    force: bool = False,
) -> Path:
    """Scaffold a new custom MCP server definition.

    Args:
        name: Server name.
        config: Server configuration dict.  Uses an empty scaffold when
            ``None``.
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

    server_config = config if config is not None else {"command": "", "args": []}
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


_LEGACY_MANAGED_KEY = "_vaultspecManaged"
_TOML_BLOCK_TYPE = "mcps"
_STDIO_FIELDS = frozenset({"command", "args", "env"})


def _normalized_sources(
    sources: dict[str, tuple[Path, dict[str, Any]]],
    target: McpTarget,
    result: SyncResult,
) -> dict[str, tuple[Path, dict[str, Any]]]:
    """Validate canonical stdio definitions before a provider adapter sees them."""
    normalized: dict[str, tuple[Path, dict[str, Any]]] = {}
    for name, (path, config) in sources.items():
        unsupported = sorted(set(config) - _STDIO_FIELDS)
        command = config.get("command")
        args = config.get("args", [])
        env = config.get("env", {})
        if unsupported:
            result.warnings.append(
                f"MCP server '{name}' has fields unsupported by "
                f"{target.provider.value}: {unsupported}; skipping this target."
            )
            continue
        if not isinstance(command, str):
            result.warnings.append(
                f"MCP server '{name}' has a non-string command; skipping "
                f"{target.provider.value}."
            )
            continue
        if not isinstance(args, list) or not all(
            isinstance(item, str) for item in args
        ):
            result.warnings.append(
                f"MCP server '{name}' has non-string args; skipping "
                f"{target.provider.value}."
            )
            continue
        if not isinstance(env, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in env.items()
        ):
            result.warnings.append(
                f"MCP server '{name}' has a non-string environment map; skipping "
                f"{target.provider.value}."
            )
            continue
        definition: dict[str, Any] = {"command": command}
        if "args" in config:
            definition["args"] = list(args)
        if "env" in config:
            definition["env"] = dict(env)
        normalized[name] = (path, definition)
    return normalized


def _fingerprint(config: dict[str, Any]) -> str:
    """Return the stable observed-content fingerprint stored in ownership state."""
    encoded = json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _owned_names(state: dict[str, Any], target: McpTarget) -> set[str]:
    raw = state["targets"].get(_ownership_target_key(target), {})
    managed = raw.get("managed", {}) if isinstance(raw, dict) else {}
    if isinstance(managed, dict):
        return {str(name) for name in managed}
    return set()


def _owned_fingerprints(state: dict[str, Any], target: McpTarget) -> dict[str, str]:
    """Return the recorded name-to-fingerprint map for one target's managed entries.

    A name present here with a matching current fingerprint proves the deployed
    entry is byte-identical to what vaultspec last wrote, so it is safe to
    refresh to the current canonical shape without ``--force``. A name absent
    from this map (legacy name-only ownership record) cannot be verified and
    keeps the existing skip-and-warn behavior.
    """
    raw = state["targets"].get(_ownership_target_key(target), {})
    managed = raw.get("managed", {}) if isinstance(raw, dict) else {}
    if isinstance(managed, dict):
        return {
            str(name): value
            for name, value in managed.items()
            if isinstance(value, str)
        }
    return {}


def _launch_repr(config: dict[str, Any]) -> str:
    """Return a human-readable one-line rendering of a server's launch command."""
    command = str(config.get("command", ""))
    args = config.get("args", [])
    parts = (
        [command, *(str(item) for item in args)]
        if isinstance(args, list)
        else [command]
    )
    return " ".join(part for part in parts if part)


def _set_owned_names(
    state: dict[str, Any], target: McpTarget, servers: dict[str, dict[str, Any]]
) -> None:
    key = _ownership_target_key(target)
    if not servers:
        state["targets"].pop(key, None)
        return
    state["targets"][key] = {
        "provider": target.provider.value,
        "scope": target.scope.value,
        "path": str(target.path.resolve()),
        "managed": {
            name: _fingerprint(config) for name, config in sorted(servers.items())
        },
    }


def _discard_owned_names(
    state: dict[str, Any], target: McpTarget, names: set[str]
) -> None:
    key = _ownership_target_key(target)
    record = state["targets"].get(key)
    if not isinstance(record, dict):
        return
    managed = record.get("managed")
    if not isinstance(managed, dict):
        state["targets"].pop(key, None)
        return
    for name in names:
        managed.pop(name, None)
    if not managed:
        state["targets"].pop(key, None)


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


def _json_server_map(
    raw: dict[str, Any], target: McpTarget, root: Path
) -> dict[str, Any]:
    """Return the native JSON server map for a Claude/Antigravity target."""
    container = raw
    if target.provider is Tool.CLAUDE and target.scope is McpScope.LOCAL:
        projects = raw.setdefault("projects", {})
        if not isinstance(projects, dict):
            raise VaultSpecError(
                "Claude configuration field 'projects' is not an object."
            )
        project = projects.setdefault(root.resolve().as_posix(), {})
        if not isinstance(project, dict):
            raise VaultSpecError("Claude local project configuration is not an object.")
        container = project
    servers = container.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        raise VaultSpecError(f"MCP server map in {target.path} is not an object.")
    return servers


def _drop_empty_json_server_map(
    raw: dict[str, Any], target: McpTarget, root: Path
) -> None:
    """Remove empty native containers while retaining unrelated host settings."""
    if target.provider is Tool.CLAUDE and target.scope is McpScope.LOCAL:
        projects = raw.get("projects")
        if not isinstance(projects, dict):
            return
        project_key = root.resolve().as_posix()
        project = projects.get(project_key)
        if isinstance(project, dict) and not project.get("mcpServers"):
            project.pop("mcpServers", None)
            if not project:
                projects.pop(project_key, None)
        if not projects:
            raw.pop("projects", None)
        return
    if not raw.get("mcpServers"):
        raw.pop("mcpServers", None)


def _write_json_target(
    path: Path, raw: dict[str, Any], target: McpTarget, root: Path
) -> None:
    _drop_empty_json_server_map(raw, target, root)
    if raw:
        ensure_dir(path.parent)
        atomic_write(path, json.dumps(raw, indent=2) + "\n")
    elif path.exists():
        path.unlink()


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


def _toml_value(value: Any) -> str:
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float) and not isinstance(value, bool):
        return repr(value)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    if isinstance(value, dict):
        pairs = (
            f"{json.dumps(str(key))} = {_toml_value(item)}"
            for key, item in sorted(value.items())
        )
        return "{ " + ", ".join(pairs) + " }"
    raise VaultSpecError(
        f"Codex MCP configuration contains unsupported value: {value!r}"
    )


def _render_codex_servers(servers: dict[str, dict[str, Any]]) -> str:
    sections: list[str] = []
    for name, config in sorted(servers.items()):
        lines = [f"[mcp_servers.{json.dumps(name, ensure_ascii=False)}]"]
        lines.extend(
            f"{key} = {_toml_value(value)}" for key, value in sorted(config.items())
        )
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


def _toml_servers(content: str) -> dict[str, dict[str, Any]]:
    if not content.strip():
        return {}
    parsed = tomllib.loads(content)
    raw = parsed.get("mcp_servers", {})
    if not isinstance(raw, dict):
        raise VaultSpecError("Codex 'mcp_servers' field is not a table.")
    servers: dict[str, dict[str, Any]] = {}
    for name, config in raw.items():
        if not isinstance(config, dict):
            raise VaultSpecError(f"Codex MCP server '{name}' is not a table.")
        servers[str(name)] = dict(config)
    return servers


def _managed_toml_content(content: str) -> str:
    for block in find_blocks(content):
        if block.block_type == _TOML_BLOCK_TYPE:
            lines = content.splitlines()
            return "\n".join(lines[block.content_start - 1 : block.content_end])
    return ""


_TOML_TABLE_RE = re.compile(r"^\s*\[(?!\[)(?P<header>.+)]\s*(?:#.*)?$")


def _toml_header_path(header: str) -> tuple[str, ...] | None:
    """Parse one TOML table header into its semantic key path."""
    try:
        parsed = tomllib.loads(f"[{header}]\n_vaultspec_probe = true\n")
    except tomllib.TOMLDecodeError:
        return None
    path: list[str] = []
    current: Any = parsed
    while isinstance(current, dict) and "_vaultspec_probe" not in current:
        if len(current) != 1:
            return None
        key, current = next(iter(current.items()))
        path.append(str(key))
    return tuple(path) if isinstance(current, dict) else None


def _strip_external_codex_server(content: str, name: str) -> str:
    """Remove one external Codex server's table sections without reformatting."""
    kept: list[str] = []
    removing = False
    for line in content.splitlines():
        match = _TOML_TABLE_RE.match(line)
        if match:
            path = _toml_header_path(match.group("header"))
            removing = bool(
                path and len(path) >= 2 and path[0] == "mcp_servers" and path[1] == name
            )
        if not removing:
            kept.append(line)
    rendered = "\n".join(kept)
    if rendered and content.endswith("\n"):
        rendered += "\n"
    return rendered


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
                        raw = json.loads(target.path.read_text(encoding="utf-8"))
                        if not isinstance(raw, dict):
                            raise VaultSpecError("JSON root is not an object.")
                        servers = _json_server_map(raw, target, target_dir)
                        present = requested & set(servers)
                        sub.pruned += len(present)
                        sub.items.extend((name, "[DELETE]") for name in sorted(present))
                        if not dry_run:
                            for name in present:
                                servers.pop(name, None)
                            raw.pop(_LEGACY_MANAGED_KEY, None)
                            _write_json_target(target.path, raw, target, target_dir)
                    else:
                        content = target.path.read_text(encoding="utf-8")
                        block_servers = _toml_servers(_managed_toml_content(content))
                        present = requested & set(block_servers)
                        sub.pruned += len(present)
                        sub.items.extend((name, "[DELETE]") for name in sorted(present))
                        if not dry_run:
                            for name in present:
                                block_servers.pop(name, None)
                            rendered = _render_codex_servers(block_servers)
                            updated = (
                                upsert_block(
                                    content,
                                    _TOML_BLOCK_TYPE,
                                    rendered,
                                    comment_prefix="# ",
                                )
                                if rendered
                                else strip_block(content, _TOML_BLOCK_TYPE)
                            )
                            if updated:
                                atomic_write(target.path, updated)
                            else:
                                target.path.unlink()
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
