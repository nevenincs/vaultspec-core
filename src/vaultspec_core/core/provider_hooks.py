"""Author agent-runtime hooks once and render them per provider.

This module is distinct from :mod:`vaultspec_core.hooks`, which handles
vaultspec's own CLI-lifecycle events (``vault.document.created`` etc.) that
fire inside the vaultspec runtime. *Provider hooks* are agent-runtime
tool-lifecycle hooks (pre/post tool use, session start/stop, ...) consumed by
the coding agents themselves - Claude Code, OpenAI Codex, the Antigravity CLI
(``agy``), and the Gemini CLI.

Every provider verified (mid-2026) shares the same structural shape - an event
maps to a list of matcher groups, each with a list of ``{"type": "command",
"command": ...}`` handlers - but the providers disagree on event names, file
location, and packaging:

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
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from . import types as _t
from .enums import DirName, ProviderCapability, Tool
from .helpers import atomic_write, ensure_dir
from .types import SyncResult

logger = logging.getLogger(__name__)

__all__ = [
    "PROVIDER_EVENT_NAMES",
    "HookEvent",
    "HookSpec",
    "load_provider_hook_specs",
    "provider_hooks_sync",
    "render_hooks_payload",
    "supported_events",
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
        HookEvent.STOP: "Stop",
        # Codex has no SessionEnd or Notification hook events.
    },
    Tool.ANTIGRAVITY: {
        HookEvent.PRE_TOOL_USE: "PreToolUse",
        HookEvent.POST_TOOL_USE: "PostToolUse",
        HookEvent.SESSION_START: "SessionStart",
        HookEvent.SESSION_END: "SessionEnd",
        HookEvent.STOP: "Stop",
        HookEvent.NOTIFICATION: "Notification",
        # agy has no UserPromptSubmit hook event.
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

# The named hookset agy groups vaultspec-managed hooks under in hooks.json.
_AGY_HOOKSET_NAME = "vaultspec"


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
    """

    name: str
    event: HookEvent
    command: str
    matcher: str = ""
    timeout: int | None = None
    enabled: bool = True


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
        return {_AGY_HOOKSET_NAME: {"enabled": True, **grouped}}
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
        for action in actions:
            if isinstance(action, dict) and action.get("type") == "shell":
                cmd = action.get("command")
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
    :mod:`vaultspec_core.hooks`. Returns specs sorted by source filename stem
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
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            msg = f"Failed to parse hook {path.name}: {exc}"
            logger.warning(msg)
            if warnings is not None:
                warnings.append(msg)
            continue
        if not isinstance(data, dict):
            continue
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
            )
        )
    return specs


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
    return raw if isinstance(raw, dict) else {}


def _compose_flat_hooks(
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
    hooks: dict[str, Any] = dict(raw_hooks) if isinstance(raw_hooks, dict) else {}

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
        out[_AGY_HOOKSET_NAME] = payload[_AGY_HOOKSET_NAME]
    else:
        out.pop(_AGY_HOOKSET_NAME, None)
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
        composed, new_managed = _compose_flat_hooks(existing, prev_managed, payload)

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


def provider_hooks_sync(dry_run: bool = False) -> SyncResult:
    """Render provider hooks into every installed hook-capable provider.

    Loads canonical hook specs once and renders them into each installed
    provider that declares the ``HOOKS`` capability, writing the provider's
    native hook-config file with ownership tracking so user-authored hooks are
    preserved.

    Args:
        dry_run: When ``True``, compute actions without writing.

    Returns:
        Accumulated :class:`SyncResult`, with per-provider results under
        ``per_tool``.
    """
    from .manifest import installed_tool_configs

    total = SyncResult()
    parse_warnings: list[str] = []
    specs = load_provider_hook_specs(warnings=parse_warnings)
    total.warnings.extend(parse_warnings)

    target_dir = _t.get_context().target_dir
    for tool, cfg in installed_tool_configs().items():
        if ProviderCapability.HOOKS not in cfg.capabilities:
            continue
        if tool not in _HOOK_FILES:
            continue
        result = _sync_one(tool, target_dir, specs, dry_run=dry_run)
        total.merge(result)
        total.per_tool[tool.value] = result
    return total
