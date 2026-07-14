"""Manage MCP server definitions for the vaultspec framework.

This module handles MCP server definition collection, custom definition
scaffolding, and the merge pipeline that syncs definitions into ``.mcp.json``.
Unlike rules/skills/agents (which use Markdown sources and per-tool directory
sync), MCP definitions are JSON files merged into a single provider-agnostic
``.mcp.json`` file.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from . import types as _t
from .enums import InstallMode, render_mode
from .exceptions import ResourceExistsError, ResourceNotFoundError, VaultSpecError
from .helpers import advisory_lock, atomic_write, ensure_dir
from .types import SyncResult

logger = logging.getLogger(__name__)

#: Sentinel tokens carried by the mode-neutral builtin MCP definition
#: (``builtins/mcps/vaultspec-core.builtin.json``). They are deliberately
#: shaped so they cannot collide with any real command name or argument value,
#: so :func:`render_mcp_definition_for_mode` can detect and substitute them
#: unambiguously. The seeded ``.vaultspec/mcps/`` copy carries these same bytes
#: (keeping the ``BuiltinVersionSignal`` snapshot hash stable); substitution
#: happens only here, downstream, and only the substituted concrete command is
#: ever written into a workspace ``.mcp.json``.
_MODE_COMMAND_TOKEN = "@@VAULTSPEC_INSTALL_MODE_COMMAND@@"
_MODE_ARGS_TOKEN = "@@VAULTSPEC_INSTALL_MODE_ARGS@@"

#: Optional metadata keys a mode-neutral MCP definition may carry alongside the
#: sentinel tokens to name the distribution and runnable module its launch
#: renders for. Absent on core's own builtin - which defaults to core's package
#: and module below, keeping that file byte-identical - and present on a
#: companion package's builtin so core's single sentinel-substitution renderer
#: produces *that* package's ``uv run``/``uvx`` launch without a second renderer.
#: They are consumed and stripped during substitution, so they never reach the
#: written ``.mcp.json``.
_MODE_PACKAGE_KEY = "_vaultspec_mode_package"
_MODE_MODULE_KEY = "_vaultspec_mode_module"

#: The distribution and module core's own MCP server launches through. Used as
#: the substitution defaults when a definition omits the per-definition
#: package/module keys, so core's token-only builtin renders exactly as before.
_DEFAULT_MCP_PACKAGE = "vaultspec-core"
_DEFAULT_MCP_MODULE = "vaultspec_core.mcp_server.app"


def render_launch_for_mode(
    mode: InstallMode, package: str, module: str
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
    own venv (``uv run python -m <module>``), byte-identical to the launch every
    dependency-mode workspace has always synced. Tool mode launches the same
    module through an ephemeral ``uvx --from <package>`` invocation so the
    distribution never enters the governed project's dependency set.

    Args:
        mode: The provisioning mode whose launch to render.
        package: Distribution name for the ``uvx --from`` tool-mode launch.
        module: Fully-qualified module the MCP server runs as ``python -m``.

    Returns:
        The ``(command, args)`` pair for the rendered mode.
    """
    if render_mode(mode) is InstallMode.DEPENDENCY:
        return "uv", ["run", "python", "-m", module]
    return "uvx", ["--from", package, "python", "-m", module]


#: Core's own concrete MCP-server launch per mode, derived from the generalized
#: :func:`render_launch_for_mode` so this convenience table and the renderer can
#: never drift. Dependency mode reproduces byte-for-byte the launch every
#: dependency-mode workspace has always synced; tool mode launches the same
#: module entry point through an ephemeral ``uvx`` invocation. Only the two
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
    core's package and module when absent; those keys are stripped during
    substitution so they never reach the written ``.mcp.json``.

    Args:
        definition: A parsed MCP server definition (``command``/``args`` map).
        mode: The provisioning mode whose concrete launch to substitute.

    Returns:
        A shallow copy of *definition* with the tokens replaced by the
        mode-specific launch command and args and the substitution-metadata keys
        removed. The input is not mutated.
    """
    rendered = dict(definition)
    has_command_token = rendered.get("command") == _MODE_COMMAND_TOKEN
    has_args_token = rendered.get("args") == [_MODE_ARGS_TOKEN]
    if not (has_command_token or has_args_token):
        return rendered
    package = str(rendered.pop(_MODE_PACKAGE_KEY, _DEFAULT_MCP_PACKAGE))
    module = str(rendered.pop(_MODE_MODULE_KEY, _DEFAULT_MCP_MODULE))
    command, args = render_launch_for_mode(mode, package, module)
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


def _existing_source_server_names() -> set[str]:
    """Return server names whose source file physically exists on disk.

    Unlike :func:`collect_mcp_servers`, this never opens or parses the
    JSON files — a definition that exists but currently fails to parse
    (e.g. transient typo) is still reported as present. This is the
    correct signal for the prune step in :func:`mcp_sync`: a server
    must only be considered for orphan removal when its source file
    is *definitively absent*, not when parsing happened to fail this
    run. Otherwise a single typo in a managed definition would
    silently delete the corresponding ``.mcp.json`` entry on the next
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
    form for every entry into every ``.mcp.json`` target. When *mode* is
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


def mcp_status() -> dict[str, Any]:
    """Return focused status for MCP definitions and the synced config file.

    This is intentionally narrower than ``spec doctor``: it reports only
    whether source definitions under ``.vaultspec/mcps/`` are represented
    in the workspace ``.mcp.json`` and whether managed entries have drifted.

    Drift is judged mode-aware: definitions are rendered for the workspace's
    resolved render mode (via
    :func:`~vaultspec_core.core.workspace_mode.resolve_render_mode`) before
    they are compared against the synced ``.mcp.json`` entries, so a
    correctly-provisioned workspace in either mode is not reported as drifted
    against the mode-neutral token form.
    """
    try:
        target_dir = _t.get_context().target_dir
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
            "warnings": ["No workspace context available for MCP status."],
        }

    from .workspace_mode import CORE_DISTRIBUTION_NAME, resolve_render_mode

    render_mode = resolve_render_mode(target_dir, package=CORE_DISTRIBUTION_NAME)
    parse_warnings: list[str] = []
    sources = collect_mcp_servers(
        warnings=parse_warnings, mode=render_mode, target=target_dir
    )
    definitions = sorted(sources)

    mcp_json = target_dir / ".mcp.json"
    configured: list[str] = []
    managed: list[str] = []
    missing = definitions.copy()
    drifted: list[str] = []
    stale_managed: list[str] = []
    warnings = list(parse_warnings)
    status = "ok"

    if not mcp_json.exists():
        status = "missing_config" if definitions else "no_definitions"
        warnings.append(".mcp.json is missing; run vaultspec-core sync.")
        return {
            "status": status,
            "config_path": str(mcp_json),
            "config_exists": False,
            "definitions": definitions,
            "configured": configured,
            "managed": managed,
            "missing": missing,
            "drifted": drifted,
            "stale_managed": stale_managed,
            "warnings": warnings,
        }

    try:
        raw = json.loads(mcp_json.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return {
            "status": "invalid_config",
            "config_path": str(mcp_json),
            "config_exists": True,
            "definitions": definitions,
            "configured": configured,
            "managed": managed,
            "missing": missing,
            "drifted": drifted,
            "stale_managed": stale_managed,
            "warnings": [*warnings, f"Cannot parse .mcp.json: {exc}"],
        }

    if not isinstance(raw, dict):
        return {
            "status": "invalid_config",
            "config_path": str(mcp_json),
            "config_exists": True,
            "definitions": definitions,
            "configured": configured,
            "managed": managed,
            "missing": missing,
            "drifted": drifted,
            "stale_managed": stale_managed,
            "warnings": [*warnings, ".mcp.json is not a JSON object."],
        }

    servers = raw.get("mcpServers", {})
    if not isinstance(servers, dict):
        status = "invalid_config"
        warnings.append(".mcp.json field 'mcpServers' is not a JSON object.")
        servers = {}

    configured = sorted(str(name) for name in servers)
    raw_managed = raw.get(_MANAGED_KEY, [])
    if isinstance(raw_managed, list):
        managed = sorted(str(name) for name in raw_managed if isinstance(name, str))

    missing = [name for name in definitions if name not in servers]
    for name, (_source_path, config) in sources.items():
        if name in servers and name in managed and servers[name] != config:
            drifted.append(name)
    stale_managed = [name for name in managed if name not in definitions]

    if status == "ok" and (missing or drifted or stale_managed or warnings):
        status = "partial"

    return {
        "status": status,
        "config_path": str(mcp_json),
        "config_exists": True,
        "definitions": definitions,
        "configured": configured,
        "managed": managed,
        "missing": missing,
        "drifted": sorted(drifted),
        "stale_managed": stale_managed,
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


_MANAGED_KEY = "_vaultspecManaged"


def _apply_mcp_merge(
    existing: dict[str, Any],
    sources: dict[str, tuple[Path, dict[str, Any]]],
    *,
    force: bool,
    prune: bool,
    result: SyncResult,
    label: str,
    force_managed: frozenset[str] = frozenset(),
) -> bool:
    """Merge *sources* into the *existing* MCP config dict in place.

    Shared merge engine for every MCP target file (the workspace
    ``.mcp.json`` and each provider-native config such as Antigravity's
    ``.agents/mcp_config.json``). Mutates *existing* (its ``mcpServers`` map
    and the ``_vaultspecManaged`` ownership sidecar) and records actions and
    warnings on *result*.

    *force_managed* is a surgical, per-entry escalation of *force* scoped to
    the named already-managed servers only. It exists for the ``install
    --upgrade`` mode-flip case: when an upgrade flips the workspace's install
    mode, the pre-commit and declaration renderers rewrite unconditionally but
    an unforced MCP sync would skip a pre-existing managed ``vaultspec-core``
    entry still carrying the old mode's launch shape, leaving the migration
    non-atomic across the three renderers. Naming that entry in *force_managed*
    updates it in the same run without escalating the whole sync to *force*.
    Because it gates only the ``name in managed`` branch, a user-owned entry
    that shares a name with a source is never adopted or overwritten by it, so
    the foreign-entry discipline stays intact.

    Args:
        existing: Parsed target config; mutated in place.
        sources: Collected MCP definitions keyed by server name.
        force: Overwrite managed/user entries that differ from their source.
        prune: Remove managed entries whose source file is gone from disk.
        result: Accumulator for counters, items, and warnings.
        label: Human label for the target (e.g. ``".mcp.json"``) used in
            warning messages.
        force_managed: Names of already-managed servers to overwrite when they
            diverge from their source, even when *force* is ``False``. Ignored
            for any name not currently in the managed set.

    Returns:
        ``True`` when *existing* was modified, else ``False``.
    """
    servers = existing.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        servers = {}
        existing["mcpServers"] = servers

    if _MANAGED_KEY in existing:
        raw_managed = existing.get(_MANAGED_KEY, [])
        if isinstance(raw_managed, list):
            managed: set[str] = {str(n) for n in raw_managed if isinstance(n, str)}
        else:
            managed = set()
    else:
        # Legacy migration: workspaces created before ownership tracking
        # shipped have no sidecar key. Treat any pre-existing entry whose
        # name matches a current source as managed — preserving the legacy
        # "differs, use --force" warning behaviour for already-installed
        # entries. After this sync the sidecar is written and future syncs
        # use strict ownership.
        managed = set(servers.keys()) & set(sources.keys())
        if managed:
            msg = (
                f"Legacy {label} migration: taking ownership of "
                f"{len(managed)} pre-existing entries that match current "
                f"sources ({sorted(managed)}). Future syncs will use strict "
                f"ownership tracking."
            )
            logger.warning(msg)
            result.warnings.append(msg)

    changed = False
    for name, (_path, config) in sources.items():
        if name not in servers:
            # New entry — vaultspec creates it and takes ownership.
            servers[name] = config
            managed.add(name)
            result.added += 1
            result.items.append((name, "[ADD]"))
            changed = True
        elif name in managed:
            # Previously managed by vaultspec — sync content.
            if servers[name] == config:
                result.unchanged += 1
                result.items.append((name, "[UNCHANGED]"))
            elif force or name in force_managed:
                servers[name] = config
                result.updated += 1
                result.items.append((name, "[UPDATE]"))
                changed = True
            else:
                result.skipped += 1
                result.items.append((name, "[SKIP]"))
                result.warnings.append(
                    f"MCP server '{name}' differs from definition "
                    f"(use --force to overwrite)"
                )
        elif force:
            # User-added entry that shares a name with a current source.
            # --force is the explicit adopt path (issue #120): overwrite it
            # with the source definition and take ownership, so the entry
            # converges without the user hand-editing the generated file
            # the CLI tells them not to touch.
            if servers[name] != config:
                servers[name] = config
                changed = True
            managed.add(name)
            result.updated += 1
            result.items.append((name, "[ADOPT]"))
            changed = True
        else:
            # User-added entry that shares a name with a current
            # source. Preserve it; never take ownership implicitly.
            result.skipped += 1
            result.items.append((name, "[SKIP]"))
            result.warnings.append(
                f"MCP server '{name}' is user-managed and shares its name "
                f"with a vaultspec source; skipping. Re-run with --force to "
                f"adopt it into vaultspec management, or rename one to resolve."
            )

    if prune:
        # Critical: prune is gated on the source file being *physically
        # absent* from disk, not merely missing from the parsed sources
        # dict. ``collect_mcp_servers`` omits files that exist but failed
        # JSON parsing or read; treating those as deletions would let a
        # transient typo silently destroy the corresponding entry under
        # ``sync --force``. ``_existing_source_server_names`` walks the
        # directory without opening files, so a parse failure leaves the
        # entry intact until the source is fixed (or genuinely deleted).
        on_disk = _existing_source_server_names()
        for name in sorted(managed - on_disk):
            if name in servers:
                servers.pop(name)
                result.pruned += 1
                result.items.append((name, "[DELETE]"))
                changed = True
            managed.discard(name)

    # Reconcile managed set with what is actually in ``servers``
    # (defensive cleanup against external mutations).
    managed &= set(servers.keys())

    # Persist managed set; remove the key entirely when empty so we never
    # write a dangling sidecar.
    prior_managed = existing.get(_MANAGED_KEY)
    new_managed_value = sorted(managed) if managed else None
    if new_managed_value is None:
        if _MANAGED_KEY in existing:
            del existing[_MANAGED_KEY]
            changed = True
    elif prior_managed != new_managed_value:
        existing[_MANAGED_KEY] = new_managed_value
        changed = True

    return changed


def _sync_mcp_target(
    path: Path,
    sources: dict[str, tuple[Path, dict[str, Any]]],
    *,
    dry_run: bool,
    force: bool,
    prune: bool,
    result: SyncResult,
    label: str,
    force_managed: frozenset[str] = frozenset(),
) -> None:
    """Merge *sources* into a single MCP config file at *path*.

    Reads the existing file (if any), applies the shared merge via
    :func:`_apply_mcp_merge`, and writes the result. When pruning empties
    the file and no user-defined top-level keys remain, the file is removed
    rather than left as an orphan ``{"mcpServers": {}}`` artefact.

    *force_managed* is forwarded verbatim to :func:`_apply_mcp_merge`; see its
    docstring for the narrowly-scoped mode-flip escalation it performs.
    """
    with advisory_lock(path):
        existing: dict[str, Any] = {}
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    existing = raw
            except (json.JSONDecodeError, OSError) as exc:
                result.warnings.append(f"Cannot parse existing {label}: {exc}")

        changed = _apply_mcp_merge(
            existing,
            sources,
            force=force,
            prune=prune,
            result=result,
            label=label,
            force_managed=force_managed,
        )

        if changed and not dry_run:
            servers = existing.get("mcpServers", {})
            if not servers and len(existing) == 1:
                if path.exists():
                    path.unlink()
            else:
                ensure_dir(path.parent)
                atomic_write(path, json.dumps(existing, indent=2) + "\n")


def _provider_mcp_targets() -> dict[str, Path]:
    """Return installed providers that read a provider-native MCP config file.

    Maps tool name to its ``mcp_config_file`` path (e.g. Antigravity's
    ``.agents/mcp_config.json``). Providers that read the shared workspace
    ``.mcp.json`` are not included.
    """
    from .manifest import installed_tool_configs

    targets: dict[str, Path] = {}
    for tool, cfg in installed_tool_configs().items():
        if cfg.mcp_config_file is not None:
            targets[tool.value] = cfg.mcp_config_file
    return targets


def mcp_sync(
    dry_run: bool = False,
    force: bool = False,
    prune: bool = False,
    mode: InstallMode | None = None,
    force_managed: frozenset[str] = frozenset(),
) -> SyncResult:
    """Sync MCP server definitions into every MCP config target.

    Collects all definitions from the MCP source directory and merges them
    into the shared workspace ``.mcp.json`` plus each installed provider's
    native MCP config file (for example Antigravity's
    ``.agents/mcp_config.json``, which uses the same ``{"mcpServers": {...}}``
    schema). When ``prune`` is set, managed entries whose source files have
    been deleted are removed from every target.

    Ownership tracking is persisted in each file under the reserved top-level
    key ``_vaultspecManaged`` (a sorted list of server names vaultspec
    created). Entries that pre-existed without being added by ``mcp_sync``
    never enter the managed set, so user-added servers are always preserved —
    even if they share a name with a current source. This mirrors the
    content-marker ownership pattern used by ``sync_files``.

    The launch command *core's own* definition renders to is selected by
    *mode*. When *mode* is ``None`` (every standalone ``sync``/``doctor``
    caller) it is resolved from core's entry in the committed workspace
    declaration via
    :func:`~vaultspec_core.core.workspace_mode.resolve_render_mode`, whose
    legacy-absent rule renders dependency mode so a workspace provisioned
    before ``install-mode`` is never silently flipped to the ``uvx`` shape. The
    fresh-``install`` path passes its resolved mode explicitly, because the
    declaration is written only after this render runs. Every *companion*
    definition (one that names its own declaring package) instead renders at
    that package's own committed render mode, so a mixed-mode workspace syncs
    each managed entry in its own shape rather than flattening every entry onto
    core's mode; see :func:`collect_mcp_servers` and
    :func:`_render_definition_for_sync`.

    Args:
        dry_run: If ``True``, compute changes without writing.
        force: Overwrite entries that differ from their definitions.
        prune: If ``True``, remove managed entries whose source files have
            been deleted. Mirrors ``rules_sync``/``agents_sync``.
        mode: Provisioning mode to render definitions for, or ``None`` to
            resolve it from the committed workspace declaration.
        force_managed: Names of already-managed servers to overwrite when they
            diverge from their source, even when *force* is ``False``. This is
            the ``install --upgrade`` mode-flip seam: it lets the caller migrate
            a specific managed entry (the ``vaultspec-core`` launch command) to
            the newly-resolved mode's shape in the same run without escalating
            the whole sync to *force*. Scoped to managed entries only, so
            user-owned entries stay untouched.

    Returns:
        :class:`~vaultspec_core.core.types.SyncResult` with sync statistics.
        Per-provider MCP-file results are recorded under ``per_tool``.
    """
    result = SyncResult()

    try:
        target_dir = _t.get_context().target_dir
    except LookupError:
        result.errors.append("No workspace context available for MCP sync.")
        return result

    if mode is None:
        from .workspace_mode import CORE_DISTRIBUTION_NAME, resolve_render_mode

        mode = resolve_render_mode(target_dir, package=CORE_DISTRIBUTION_NAME)

    parse_warnings: list[str] = []
    sources = collect_mcp_servers(warnings=parse_warnings, mode=mode, target=target_dir)
    result.warnings.extend(parse_warnings)

    _sync_mcp_target(
        target_dir / ".mcp.json",
        sources,
        dry_run=dry_run,
        force=force,
        prune=prune,
        result=result,
        label=".mcp.json",
        force_managed=force_managed,
    )

    for tool_name, mcp_path in sorted(_provider_mcp_targets().items()):
        sub = SyncResult()
        rel = (
            str(mcp_path.relative_to(target_dir))
            if mcp_path.is_relative_to(target_dir)
            else str(mcp_path)
        )
        _sync_mcp_target(
            mcp_path,
            sources,
            dry_run=dry_run,
            force=force,
            prune=prune,
            result=sub,
            label=rel.replace("\\", "/"),
            force_managed=force_managed,
        )
        result.merge(sub)
        result.per_tool[tool_name] = sub

    return result


def mcp_uninstall(target_dir: Path, *, dry_run: bool = False) -> list[str]:
    """Remove all registry-managed MCP entries from ``.mcp.json``.

    Collects managed server names from the registry source directory and
    removes each from ``.mcp.json``.  User-added entries are preserved.
    If no servers remain, the file is deleted.

    Args:
        target_dir: Workspace root directory.
        dry_run: When ``True``, returns names without modifying files.

    Returns:
        List of server names that were (or would be) removed.
    """
    sources = collect_mcp_servers()
    managed_names = set(sources.keys())

    # If no registry is available, fall back to removing known built-in names
    if not managed_names:
        managed_names = {"vaultspec-core"}

    # Every MCP target: the shared .mcp.json plus each installed provider's
    # native MCP config (e.g. Antigravity's .agents/mcp_config.json).
    targets = [target_dir / ".mcp.json", *_provider_mcp_targets().values()]

    removed: set[str] = set()
    for mcp_path in targets:
        if not mcp_path.exists():
            continue
        with advisory_lock(mcp_path):
            try:
                raw = json.loads(mcp_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if not isinstance(raw, dict):
                continue
            servers = raw.get("mcpServers", {})
            if not isinstance(servers, dict):
                continue

            file_removed: list[str] = []
            for name in managed_names:
                if name in servers:
                    file_removed.append(name)
                    if not dry_run:
                        del servers[name]
            if not file_removed:
                continue
            removed.update(file_removed)

            if not dry_run:
                managed = raw.get(_MANAGED_KEY)
                if isinstance(managed, list):
                    raw[_MANAGED_KEY] = [n for n in managed if n in servers]
                    if not raw[_MANAGED_KEY]:
                        del raw[_MANAGED_KEY]
                if servers or (len(raw) > 1):
                    atomic_write(mcp_path, json.dumps(raw, indent=2) + "\n")
                else:
                    mcp_path.unlink()

    return sorted(removed)
