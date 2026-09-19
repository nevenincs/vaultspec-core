"""Author agent-runtime hooks once and render them per provider.

This module is distinct from :mod:`vaultspec_core.triggers`, which handles
vaultspec's own CLI-lifecycle events (``vault.document.created`` etc.) that
fire inside the vaultspec runtime. *Provider hooks* are agent-runtime
tool-lifecycle hooks (pre/post tool use, session start/stop, ...) consumed by
the coding agents themselves - Claude Code, OpenAI Codex, the Antigravity CLI
(``agy``), and the Gemini CLI.

Providers broadly share one structural shape - an event maps to a list of
matcher groups, each with a list of ``{"type": "command", "command": ...}``
handlers - but they disagree on event names, file location, packaging, and, in
agy's case, on the shape itself for non-tool events:

============  ==========================================  ==================
Provider      File                                        Pre/post tool event
============  ==========================================  ==================
claude        ``.claude/settings.json`` (``hooks`` key)   PreToolUse/PostToolUse
codex         ``.codex/hooks.json``                       PreToolUse/PostToolUse
antigravity   ``.agents/hooks.json`` (named hooksets)     PreToolUse/PostToolUse
gemini        ``.gemini/settings.json`` (``hooks`` key)   BeforeTool/AfterTool
============  ==========================================  ==================

Authors write a canonical :class:`HookEvent`; each provider renderer maps it to
the native name (or drops it, with a warning, when the provider lacks an
equivalent), converts the timeout to the provider's unit, and emits the native
structure.

A mapping to an event a provider does not actually fire is the failure mode
this module is most exposed to: the file is written, the sync reports success,
and the hook never runs. The tables below were checked against each provider's
published hook reference; claude, codex, gemini and antigravity were verified,
and a table cell is only as good as that check.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

from . import types as _t
from .enums import DirName, ProviderCapability, Tool
from .helpers import atomic_write, ensure_dir
from .types import SyncResult

logger = logging.getLogger(__name__)

__all__ = [
    "AGY_HOOKSET_NAME",
    "PROVIDER_EVENT_NAMES",
    "HookEvent",
    "HookSpec",
    "compose_flat_hooks",
    "hook_targets",
    "load_provider_hook_specs",
    "provider_hooks_sync",
    "render_hooks_payload",
    "supported_events",
    "trusted_specs",
]


class HookEvent(StrEnum):
    """Canonical, provider-agnostic agent-runtime hook events.

    These are the vocabulary authors use in hook source files. Each provider
    renderer maps them to the provider's native event name via
    :data:`PROVIDER_EVENT_NAMES`.
    """

    PRE_TOOL_USE = "pre_tool_use"
    POST_TOOL_USE = "post_tool_use"
    USER_PROMPT_SUBMIT = "user_prompt_submit"
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    STOP = "stop"
    NOTIFICATION = "notification"


# Per-provider native event names. A missing key means the provider has no
# equivalent for that canonical event, so hooks bound to it are skipped (with a
# warning) when rendering for that provider. Verified mid-2026 against each
# provider's official hooks documentation; see the module docstring.
PROVIDER_EVENT_NAMES: dict[Tool, dict[HookEvent, str]] = {
    Tool.CLAUDE: {
        HookEvent.PRE_TOOL_USE: "PreToolUse",
        HookEvent.POST_TOOL_USE: "PostToolUse",
        HookEvent.USER_PROMPT_SUBMIT: "UserPromptSubmit",
        HookEvent.SESSION_START: "SessionStart",
        HookEvent.SESSION_END: "SessionEnd",
        HookEvent.STOP: "Stop",
        HookEvent.NOTIFICATION: "Notification",
    },
    Tool.CODEX: {
        HookEvent.PRE_TOOL_USE: "PreToolUse",
        HookEvent.POST_TOOL_USE: "PostToolUse",
        HookEvent.USER_PROMPT_SUBMIT: "UserPromptSubmit",
        HookEvent.SESSION_START: "SessionStart",
        HookEvent.SESSION_END: "SessionEnd",
        HookEvent.STOP: "Stop",
        # Codex has no Notification hook event.
    },
    Tool.ANTIGRAVITY: {
        HookEvent.PRE_TOOL_USE: "PreToolUse",
        HookEvent.POST_TOOL_USE: "PostToolUse",
        HookEvent.STOP: "Stop",
        # agy fires exactly five events: PreInvocation, PostInvocation,
        # PreToolUse, PostToolUse, Stop. SessionStart, SessionEnd and
        # Notification were mapped here and exist nowhere in the binary, so
        # those hooks rendered into .agents/hooks.json under names nothing
        # fires - no error, no warning, and no execution. PreInvocation and
        # PostInvocation are the nearest thing to a session boundary, but they
        # carry a different response contract, so they stay unmapped rather
        # than trading three silent no-ops for one malformed reply.
    },
    Tool.GEMINI: {
        HookEvent.PRE_TOOL_USE: "BeforeTool",
        HookEvent.POST_TOOL_USE: "AfterTool",
        HookEvent.SESSION_START: "SessionStart",
        HookEvent.SESSION_END: "SessionEnd",
        HookEvent.NOTIFICATION: "Notification",
        # gemini-cli uses Before/After naming; no Stop or UserPromptSubmit.
    },
}

# Timeout units differ: gemini-cli expresses hook timeouts in milliseconds,
# every other provider in seconds. Authors always write seconds.
_MILLISECOND_TIMEOUT_TOOLS = frozenset({Tool.GEMINI})

#: agy events whose value is a flat list of handlers rather than a list of
#: matcher groups. Its tool events take the matcher-group shape every other
#: provider uses; its non-tool events do not, and a matcher group written under
#: one is not a handler agy can run.
_AGY_FLAT_EVENTS = frozenset({"PreInvocation", "PostInvocation", "Stop"})

# The named hookset agy groups vaultspec-managed hooks under in hooks.json.
# Public: agy records ownership by owning this hookset rather than by writing a
# sidecar, so a status surface needs the name to find a stale one left behind
# when nothing renders any more and no payload can name it for pruning.
AGY_HOOKSET_NAME = "vaultspec"


@dataclass(frozen=True)
class HookSpec:
    """A single canonical provider-hook definition.

    Attributes:
        name: Stable identifier (the source file stem).
        event: Canonical :class:`HookEvent` that triggers the hook.
        command: Shell command the provider runs when the event fires.
        matcher: Tool-name pattern the event is filtered by (empty matches
            all). Only meaningful for tool events; ignored by providers for
            non-tool events but preserved verbatim.
        timeout: Optional timeout in seconds (converted per provider).
        enabled: When ``False`` the hook is parsed but never rendered.
        source_path: File this spec was parsed from. Consent is keyed by
            resolved path and content digest, so a spec with no source path
            cannot be matched against the ledger and is never trusted.
    """

    name: str
    event: HookEvent
    command: str
    matcher: str = ""
    timeout: int | None = None
    enabled: bool = True
    source_path: Path | None = None


def supported_events(tool: Tool) -> frozenset[HookEvent]:
    """Return the canonical events *tool* can consume."""
    return frozenset(PROVIDER_EVENT_NAMES.get(tool, {}))


def _handler(spec: HookSpec, tool: Tool) -> dict[str, Any]:
    """Build the native ``{"type": "command", ...}`` handler object."""
    handler: dict[str, Any] = {"type": "command", "command": spec.command}
    if spec.timeout is not None:
        if tool in _MILLISECOND_TIMEOUT_TOOLS:
            handler["timeout"] = spec.timeout * 1000
        else:
            handler["timeout"] = spec.timeout
    return handler


def _event_groups(
    specs: list[HookSpec], tool: Tool, warnings: list[str] | None
) -> dict[str, list[dict[str, Any]]]:
    """Group enabled specs by native event name into matcher groups.

    Specs bound to an event the provider does not support are skipped and, if
    *warnings* is provided, reported. Returns a mapping of native event name to
    a list of ``{"matcher": ..., "hooks": [...]}`` groups (one group per spec).
    """
    names = PROVIDER_EVENT_NAMES.get(tool, {})
    grouped: dict[str, list[dict[str, Any]]] = {}
    for spec in specs:
        if not spec.enabled:
            continue
        native = names.get(spec.event)
        if native is None:
            msg = (
                f"Hook {spec.name!r}: event {spec.event.value!r} has no "
                f"{tool.value} equivalent; skipping."
            )
            logger.warning(msg)
            if warnings is not None:
                warnings.append(msg)
            continue
        group: dict[str, Any] = {}
        if spec.matcher:
            group["matcher"] = spec.matcher
        group["hooks"] = [_handler(spec, tool)]
        grouped.setdefault(native, []).append(group)
    return grouped


def render_hooks_payload(
    specs: list[HookSpec], tool: Tool, warnings: list[str] | None = None
) -> dict[str, Any] | None:
    """Render canonical hooks into *tool*'s native payload structure.

    Returns the JSON-serializable object to write (or merge) for the provider,
    or ``None`` when no enabled spec maps to a supported event. The shape is
    the provider-native one:

    - antigravity: ``{"vaultspec": {"enabled": True, "<Event>": [...]}}``
    - claude / codex / gemini: ``{"<Event>": [...]}`` (the value of a ``hooks``
      key for the settings-file providers; the whole ``hooks.json`` body, under
      a ``hooks`` key, for codex)

    Args:
        specs: Canonical hook specs to render.
        tool: Target provider.
        warnings: Optional accumulator for skipped-event advisories.

    Returns:
        Native payload, or ``None`` if nothing renders.
    """
    grouped = _event_groups(specs, tool, warnings)
    if not grouped:
        return None

    if tool is Tool.ANTIGRAVITY:
        shaped: dict[str, Any] = {}
        for native, groups in grouped.items():
            if native in _AGY_FLAT_EVENTS:
                shaped[native] = [
                    handler for group in groups for handler in group["hooks"]
                ]
            else:
                shaped[native] = groups
        return {AGY_HOOKSET_NAME: {"enabled": True, **shaped}}
    return dict(grouped)


# ---------------------------------------------------------------------------
# Source loading
# ---------------------------------------------------------------------------

_CANONICAL_EVENTS = frozenset(e.value for e in HookEvent)


def _command_from(data: dict[str, Any]) -> str:
    """Extract the shell command from a hook mapping.

    Accepts either a top-level ``command`` string or the first shell entry of
    an ``actions`` list (mirroring the CLI-lifecycle hook format).
    """
    command = data.get("command")
    if isinstance(command, str) and command.strip():
        return command.strip()
    actions = data.get("actions")
    if isinstance(actions, list):
        action_items = cast("list[Any]", actions)
        for action in action_items:
            if isinstance(action, dict):
                action_map = cast("dict[str, Any]", action)
                if action_map.get("type") == "shell":
                    cmd = action_map.get("command")
                    if isinstance(cmd, str) and cmd.strip():
                        return cmd.strip()
    return ""


def load_provider_hook_specs(
    hooks_dir: Path | None = None, warnings: list[str] | None = None
) -> list[HookSpec]:
    """Load provider-hook specs from the hooks source directory.

    Reads ``*.yaml``/``*.yml`` files whose ``event`` is a canonical
    :class:`HookEvent`. Files whose event is not canonical are ignored here -
    they belong to the CLI-lifecycle hook system in
    :mod:`vaultspec_core.triggers`. Returns specs sorted by source filename stem
    for deterministic output.

    Args:
        hooks_dir: Directory to scan. Defaults to the active context's
            ``hooks_dir``.
        warnings: Optional accumulator for parse advisories.

    Returns:
        Sorted list of :class:`HookSpec`.
    """
    import yaml

    if hooks_dir is None:
        hooks_dir = _t.get_context().hooks_dir
    if not hooks_dir.exists():
        return []

    specs: list[HookSpec] = []
    files = sorted({*hooks_dir.glob("*.yaml"), *hooks_dir.glob("*.yml")})
    for path in files:
        try:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            msg = f"Failed to parse hook {path.name}: {exc}"
            logger.warning(msg)
            if warnings is not None:
                warnings.append(msg)
            continue
        if not isinstance(loaded, dict):
            continue
        data = cast("dict[str, Any]", loaded)
        event = data.get("event", "")
        if not isinstance(event, str) or event not in _CANONICAL_EVENTS:
            continue
        command = _command_from(data)
        if not command:
            msg = f"Provider hook {path.name!r} has no command; skipping."
            logger.warning(msg)
            if warnings is not None:
                warnings.append(msg)
            continue
        matcher = data.get("matcher", "")
        timeout = data.get("timeout")
        specs.append(
            HookSpec(
                name=path.stem,
                event=HookEvent(event),
                command=command,
                matcher=matcher.strip() if isinstance(matcher, str) else "",
                timeout=timeout if isinstance(timeout, int) else None,
                enabled=bool(data.get("enabled", True)),
                source_path=path,
            )
        )
    return specs


def trusted_specs(
    specs: list[HookSpec] | None = None, home: Path | None = None
) -> tuple[list[HookSpec], list[HookSpec]]:
    """Split hook specs into ``(trusted, refused)`` by consent-ledger lookup.

    Hook files arrive through git like the rest of ``.vaultspec/``, and a
    rendered hook runs inside the agent's own session on every matching tool
    call rather than once per sync. Rendering one is therefore gated on the
    same operator consent ledger the lifecycle triggers use, keyed by resolved
    path and content digest, so editing an approved hook or pulling a change to
    one withdraws the approval until it is granted again.

    :func:`provider_hooks_sync` calls this to decide what it renders, so a
    status surface that calls it reports the set the renderer actually skipped
    rather than reconstructing the decision and drifting from it.

    Args:
        specs: Specs to partition. Loads the workspace's own when omitted.
        home: Machine-global VaultSpec home holding the ledger. Defaults to the
            operator's real home; tests pass their own.

    Returns:
        ``(trusted, refused)``. A spec with no ``source_path`` is refused,
        because nothing can be matched against the ledger for it.
    """
    from ..triggers.trust import is_trusted

    if specs is None:
        specs = load_provider_hook_specs()
    trusted: list[HookSpec] = []
    refused: list[HookSpec] = []
    for spec in specs:
        ok = spec.source_path is not None and is_trusted(spec.source_path, home)
        (trusted if ok else refused).append(spec)
    return trusted, refused


# ---------------------------------------------------------------------------
# Per-provider sync
# ---------------------------------------------------------------------------

# Native hook-config file per provider, relative to the workspace root. The
# settings-file providers (claude, gemini) carry hooks inside a shared
# ``settings.json``; codex uses a dedicated ``hooks.json``; agy uses a
# dedicated ``hooks.json`` with named hooksets.
_HOOK_FILES: dict[Tool, tuple[str, str]] = {
    Tool.CLAUDE: (DirName.CLAUDE.value, "settings.json"),
    Tool.GEMINI: (DirName.GEMINI.value, "settings.json"),
    Tool.CODEX: (DirName.CODEX.value, "hooks.json"),
    Tool.ANTIGRAVITY: (DirName.ANTIGRAVITY.value, "hooks.json"),
}

# Per-provider ownership record. It lives in a sidecar file *beside* (not
# inside) the native hook config, because some providers - notably codex -
# enforce a strict schema and reject the entire hooks file if it carries an
# unknown top-level key. The sidecar records exactly the groups vaultspec wrote
# last sync so a re-sync removes precisely those and never disturbs
# user-authored hooks. agy needs no sidecar: it owns a named hookset.
_SIDECAR_NAME = ".vaultspec-hooks.json"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return cast("dict[str, Any]", raw)


def compose_flat_hooks(
    existing: dict[str, Any],
    prev_managed: dict[str, Any],
    payload: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Compose the next native dict for a ``hooks``-keyed provider file.

    Removes the previously vaultspec-managed groups (*prev_managed*, read from
    the sidecar), re-adds the current *payload*, and preserves every
    user-authored group and unrelated top-level key. The returned native dict
    carries **no** vaultspec ownership key. Returns ``(native, new_managed)``
    where *new_managed* is the ownership record to persist in the sidecar.
    """
    out = dict(existing)
    raw_hooks = out.get("hooks")
    hooks: dict[str, Any] = (
        dict(cast("dict[str, Any]", raw_hooks)) if isinstance(raw_hooks, dict) else {}
    )

    for event, groups in prev_managed.items():
        if event in hooks and isinstance(hooks[event], list):
            kept = [g for g in hooks[event] if g not in groups]
            if kept:
                hooks[event] = kept
            else:
                del hooks[event]

    new_managed: dict[str, Any] = {}
    if payload:
        for event, groups in payload.items():
            current = (
                list(hooks.get(event, [])) if isinstance(hooks.get(event), list) else []
            )
            for group in groups:
                if group not in current:
                    current.append(group)
            hooks[event] = current
            new_managed[event] = groups

    if hooks:
        out["hooks"] = hooks
    else:
        out.pop("hooks", None)
    # Defensive: strip any legacy in-file ownership key from older syncs.
    out.pop("_vaultspecManagedHooks", None)
    return out, new_managed


def _compose_agy_hooks(
    existing: dict[str, Any], payload: dict[str, Any] | None
) -> dict[str, Any]:
    """Compose the next ``.agents/hooks.json`` dict (named-hookset ownership)."""
    out = dict(existing)
    if payload:
        out[AGY_HOOKSET_NAME] = payload[AGY_HOOKSET_NAME]
    else:
        out.pop(AGY_HOOKSET_NAME, None)
    return out


def _write_or_remove(
    path: Path, content: dict[str, Any], previously_existed: bool, *, dry_run: bool
) -> str | None:
    """Write *content* (or remove the file when empty). Returns the action.

    Returns ``None`` when nothing changed. Used for both native files and
    sidecar ownership files.
    """
    if not content:
        if path.exists():
            if not dry_run:
                path.unlink()
            return "[DELETE]"
        return None
    action = "[UPDATE]" if previously_existed else "[ADD]"
    if not dry_run:
        ensure_dir(path.parent)
        atomic_write(path, json.dumps(content, indent=2) + "\n")
    return action


def _sync_one(
    tool: Tool, target_dir: Path, specs: list[HookSpec], *, dry_run: bool
) -> SyncResult:
    result = SyncResult()
    subdir, filename = _HOOK_FILES[tool]
    path = target_dir / subdir / filename
    rel = f"{subdir}/{filename}"

    render_warnings: list[str] = []
    payload = render_hooks_payload(specs, tool, render_warnings)
    result.warnings.extend(render_warnings)

    existing = _read_json(path)
    existed = path.exists()

    if tool is Tool.ANTIGRAVITY:
        composed = _compose_agy_hooks(existing, payload)
        sidecar_path: Path | None = None
        prev_managed: dict[str, Any] = {}
        new_managed: dict[str, Any] = {}
    else:
        sidecar_path = target_dir / subdir / _SIDECAR_NAME
        prev_managed = _read_json(sidecar_path)
        composed, new_managed = compose_flat_hooks(existing, prev_managed, payload)

    native_changed = composed != existing
    sidecar_changed = sidecar_path is not None and new_managed != prev_managed

    if not native_changed and not sidecar_changed:
        result.unchanged = 1
        return result

    action = (
        _write_or_remove(path, composed, existed, dry_run=dry_run)
        if native_changed
        else None
    )
    if sidecar_changed and sidecar_path is not None:
        _write_or_remove(
            sidecar_path, new_managed, sidecar_path.exists(), dry_run=dry_run
        )

    if action == "[DELETE]":
        result.pruned = 1
        result.items.append((rel, "[DELETE]"))
    elif action == "[UPDATE]" or (action is None and sidecar_changed):
        result.updated = 1
        if dry_run and action is not None:
            result.items.append((rel, action))
    elif action == "[ADD]":
        result.added = 1
        if dry_run:
            result.items.append((rel, action))
    else:
        result.unchanged = 1
    return result


def hook_targets() -> list[tuple[Tool, Path, Path | None]]:
    """Return every installed provider this sync renders hooks into.

    One entry per hook-capable installed provider, in sync order, as
    ``(tool, native_config_path, sidecar_path)``. The sidecar is ``None`` for
    providers that record ownership by owning a named hookset rather than by
    writing a sidecar beside the native file - currently only antigravity.

    This is the same filter :func:`provider_hooks_sync` iterates, exposed so a
    status surface reports exactly the set the renderer would write, rather
    than re-deriving the capability test and drifting from it.

    Returns:
        Hook-capable installed providers with their resolved paths. Empty when
        no installed provider declares the ``HOOKS`` capability.
    """
    from .manifest import installed_tool_configs

    target_dir = _t.get_context().target_dir
    targets: list[tuple[Tool, Path, Path | None]] = []
    for tool, cfg in installed_tool_configs().items():
        if ProviderCapability.HOOKS not in cfg.capabilities:
            continue
        if tool not in _HOOK_FILES:
            continue
        subdir, filename = _HOOK_FILES[tool]
        sidecar = (
            None if tool is Tool.ANTIGRAVITY else target_dir / subdir / _SIDECAR_NAME
        )
        targets.append((tool, target_dir / subdir / filename, sidecar))
    return targets


def provider_hooks_sync(dry_run: bool = False, home: Path | None = None) -> SyncResult:
    """Render provider hooks into every installed hook-capable provider.

    Loads canonical hook specs once and renders them into each installed
    provider that declares the ``HOOKS`` capability, writing the provider's
    native hook-config file with ownership tracking so user-authored hooks are
    preserved.

    Args:
        dry_run: When ``True``, compute actions without writing.
        home: Machine-global VaultSpec home holding the consent ledger.
            Defaults to the operator's real home, which is what every
            production caller wants; real-filesystem tests pass their own so
            they neither read nor write the operator's approvals.

    Returns:
        Accumulated :class:`SyncResult`, with per-provider results under
        ``per_tool``.
    """
    total = SyncResult()
    parse_warnings: list[str] = []
    specs = load_provider_hook_specs(warnings=parse_warnings)
    total.warnings.extend(parse_warnings)

    # Enforcement lives here rather than at the CLI, so every route into the
    # renderer is gated and not just the ones that can prompt. Refusing costs
    # the hook, never the sync: the rest of the sync is a legitimate operation
    # and still completes.
    specs, refused = trusted_specs(specs, home)
    for spec in refused:
        where = spec.source_path.name if spec.source_path else spec.name
        msg = (
            f"Hook {where!r} is not approved for this machine; not rendering it. "
            "Review it and run 'vaultspec-core spec hooks trust' to allow it."
        )
        logger.warning(msg)
        total.warnings.append(msg)

    target_dir = _t.get_context().target_dir
    for tool, _native, _sidecar in hook_targets():
        result = _sync_one(tool, target_dir, specs, dry_run=dry_run)
        total.merge(result)
        total.per_tool[tool.value] = result
    return total
