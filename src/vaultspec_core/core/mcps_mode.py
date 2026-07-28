"""Render mode-neutral MCP definitions into concrete provisioning-mode launches.

Split out of :mod:`vaultspec_core.core.mcps`. See that module's docstring for
the ownership-fingerprint convergence story this package implements.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .enums import InstallMode, render_mode

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
