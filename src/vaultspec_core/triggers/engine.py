"""Load, validate, and execute declarative vaultspec lifecycle triggers.

Runtime for YAML trigger definitions under ``.vaultspec/triggers/``. Parses
files into :class:`Trigger` / :class:`TriggerAction` models, filters by
:data:`SUPPORTED_EVENTS`, and executes shell actions with a re-entrancy guard
and a 60-second timeout. Key exports: :func:`load_triggers`, :func:`fire`,
:func:`fire_triggers`.
Re-exported via :mod:`vaultspec_core.triggers`; depends on
:func:`vaultspec_core.core.helpers.kill_process_tree` for subprocess cleanup.

Loading a trigger and running one are deliberately separate authorities. Trigger files
are shared through git like the rest of ``.vaultspec/``, so :func:`load_triggers`
parses whatever the workspace carries and every listing surface can describe it,
while :func:`trigger` spawns nothing that :mod:`vaultspec_core.triggers.trust` has
not matched against an operator consent record held outside the workspace. This
module is the single choke point for that check: every execution path in the
product reaches a subprocess through :func:`trigger`.
"""

from __future__ import annotations

import logging
import os
import shlex
import subprocess
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ..core.helpers import kill_process_tree
from .trust import partition_by_trust

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

__all__ = [
    "SUPPORTED_EVENTS",
    "Trigger",
    "TriggerAction",
    "TriggerResult",
    "fire",
    "fire_triggers",
    "load_triggers",
    "parse_yaml",
]

SUPPORTED_EVENTS = frozenset(
    {
        "vault.document.created",
        "config.synced",
        "audit.completed",
    }
)


@dataclass
class TriggerAction:
    """A single action within a trig.

    Attributes:
        action_type: Kind of action  - currently only ``"shell"`` is supported.
        command: Shell command string; used only when ``action_type`` is
            ``"shell"``.
    """

    action_type: str  # "shell"
    command: str = ""  # for shell actions


@dataclass
class Trigger:
    """A trigger definition loaded from YAML.

    Attributes:
        name: Stem of the YAML file that defined this trigger (used as identifier).
        event: Event name that triggers this trigger (must be in
            :data:`SUPPORTED_EVENTS`).
        actions: Ordered list of actions to execute when the event fires.
        enabled: When ``False`` the trigger is loaded but never triggered.
        source_path: Filesystem path to the YAML file this trigger was loaded from.
    """

    name: str
    event: str
    actions: list[TriggerAction] = field(default_factory=list)
    enabled: bool = True
    source_path: Path | None = None


@dataclass
class TriggerResult:
    """Result of executing a single trigger action.

    Attributes:
        trigger_name: Name of the trigger that produced this result.
        action_type: Type of the action that was executed (``"shell"``).
        success: ``True`` if the action completed without error.
        output: Captured stdout (shell actions).
        error: Captured stderr or exception message on failure.
    """

    trigger_name: str
    action_type: str
    success: bool
    output: str = ""
    error: str = ""


def parse_yaml(text: str) -> dict[str, Any]:
    """Parse YAML text into a dict.

    Args:
        text: Raw YAML text to parse.

    Returns:
        Parsed mapping; empty dict if the text is empty or blank.
    """
    import yaml

    return yaml.safe_load(text) or {}


def load_triggers(triggers_dir: Path) -> list[Trigger]:
    """Load all trigger definitions from the triggers directory.

    Reads ``*.yaml`` and ``*.yml`` files from ``triggers_dir`` in alphabetical
    order, parses each, and returns valid :class:`Trigger` objects.  Files that
    fail to parse or contain unsupported events are skipped with a warning.

    Args:
        triggers_dir: Directory to scan for trigger YAML files.

    Returns:
        List of parsed and validated :class:`Trigger` instances.
    """
    triggers: list[Trigger] = []

    if not triggers_dir.exists():
        return triggers

    seen: dict[str, Path] = {}
    for ext in ("*.yaml", "*.yml"):
        for path in sorted(triggers_dir.glob(ext)):
            if path.stem in seen:
                logger.warning(
                    "Duplicate trigger '%s': using %s, ignoring %s",
                    path.stem,
                    seen[path.stem].name,
                    path.name,
                )
                continue
            seen[path.stem] = path

    for path in seen.values():
        try:
            data = parse_yaml(path.read_text(encoding="utf-8"))
            trig = _parse_trigger(path, data)
            if trig is not None:
                triggers.append(trig)
        except Exception:
            logger.warning("Failed to parse trigger: %s", path.name, exc_info=True)

    return triggers


def _parse_trigger(path: Path, data: dict[str, Any]) -> Trigger | None:
    """Parse a trigger definition dict into a Trigger object.

    Args:
        path: Source YAML file path (used to derive the trigger name and for
            warning messages).
        data: Parsed YAML dict containing ``event`` and ``actions`` keys.

    Returns:
        A populated :class:`Trigger` instance, or ``None`` if the definition is
        invalid (missing event, unsupported event, etc.).
    """
    event = data.get("event", "")
    if not event:
        logger.warning("Trigger %s missing 'event' field", path.name)
        return None

    if event not in SUPPORTED_EVENTS:
        logger.warning("Trigger %s has unsupported event: %s", path.name, event)
        return None

    raw_actions = data.get("actions", [])
    actions = _parse_actions(raw_actions) if isinstance(raw_actions, list) else []

    return Trigger(
        name=path.stem,
        event=event,
        actions=actions,
        enabled=data.get("enabled", True),
        source_path=path,
    )


def _parse_actions(raw_actions: Any) -> list[TriggerAction]:
    """Parse every valid action from an untyped YAML sequence."""
    actions: list[TriggerAction] = []
    for raw in raw_actions:
        if isinstance(raw, dict):
            action = _parse_action(raw)
            if action is not None:
                actions.append(action)
    return actions


def _parse_action(raw: Any) -> TriggerAction | None:
    """Parse a single action dict into a TriggerAction.

    Args:
        raw: Dict with at minimum a ``type`` key; ``"shell"`` actions also
            require ``command``.

    Returns:
        A :class:`TriggerAction` instance, or ``None`` if the dict is missing
        required fields or has an unknown type.
    """
    action_type = raw.get("type", "")
    if action_type == "shell":
        cmd = raw.get("command", "")
        if not cmd:
            logger.warning(
                "Skipping action: shell action missing 'command' field (raw=%r)", raw
            )
            return None
        return TriggerAction(action_type="shell", command=cmd)

    logger.warning("Skipping action: unknown action type %r (raw=%r)", action_type, raw)
    return None


_triggering: set[str] = set()


def fire(
    triggers: list[Trigger],
    event: str,
    context: dict[str, str] | None = None,
    home: Path | None = None,
) -> list[TriggerResult]:
    """Trigger every trusted trigger matching the given event.

    Iterates over ``triggers``, filters to those whose ``event`` matches and
    ``enabled`` is ``True``, drops any whose command the operator has not
    consented to, and executes the remainder's actions in order.  Guards
    against re-entrant triggers for the same event.

    Consent is the gate this function will not spawn a process without.  A trigger
    file is committed content that arrives with a clone, so its own contents
    can never authorise it; :mod:`vaultspec_core.triggers.trust` answers from a
    ledger kept outside the workspace and denies on every doubt.  Skipped triggers
    are logged and produce no result, exactly as a non-matching trigger does.

    Args:
        triggers: List of loaded triggers to evaluate.
        event: Event name to match against trigger definitions.
        context: Optional mapping of ``{key}`` placeholder names to
            substitution values used in command and task templates.
        home: Machine-global VaultSpec home holding the consent ledger.
            Production callers pass nothing; real-filesystem tests pass their
            own directory so they never read the operator's ledger.

    Returns:
        List of :class:`TriggerResult` objects, one per executed action.
        Empty if no triggers matched the event or none of the matches are trusted.
    """
    if event in _triggering:
        logger.warning("Re-entrant trigger trigger blocked: %s", event)
        return []

    ctx = context or {}
    results: list[TriggerResult] = []

    candidates = [h for h in triggers if h.event == event and h.enabled]
    matching, untrusted = partition_by_trust(candidates, home)
    for trig in untrusted:
        logger.warning(
            "Trigger '%s' is not trusted in this workspace and will not run; "
            "review it and run 'vaultspec-core spec triggers trust' to allow it",
            trig.name,
        )
    if not matching:
        return results

    _triggering.add(event)
    try:
        logger.info("Triggering %d trigger(s) for event '%s'", len(matching), event)
        for trig in matching:
            for action in trig.actions:
                result = _execute_action(trig.name, action, ctx)
                results.append(result)
    finally:
        _triggering.discard(event)

    return results


def _interpolate(template: str, ctx: dict[str, str]) -> str:
    """Safely interpolate ``{key}`` placeholders in a template string.

    Args:
        template: String containing zero or more ``{key}`` placeholders.
        ctx: Mapping of placeholder names to replacement values.

    Returns:
        Template with all matching placeholders replaced by their values.
        Unrecognised placeholders are left as-is.
    """
    result = template
    for key, value in ctx.items():
        result = result.replace(f"{{{key}}}", value)
    return result


def _execute_action(
    trigger_name: str,
    action: TriggerAction,
    ctx: dict[str, str],
) -> TriggerResult:
    """Execute a single trigger action, dispatching to the correct handler.

    Args:
        trigger_name: Name of the parent trigger (used for result attribution).
        action: The action to execute.
        ctx: Template interpolation context passed through to the handler.

    Returns:
        A :class:`TriggerResult` describing the outcome.  Returns a failure
        result if ``action.action_type`` is unrecognised.
    """
    if action.action_type == "shell":
        return _execute_shell(trigger_name, action, ctx)

    return TriggerResult(
        trigger_name=trigger_name,
        action_type=action.action_type,
        success=False,
        error=f"Unknown action type: {action.action_type}",
    )


def _execute_shell(
    trigger_name: str,
    action: TriggerAction,
    ctx: dict[str, str],
) -> TriggerResult:
    """Execute a shell command action.

    Interpolates ``{key}`` placeholders in the command string, then runs it
    via ``subprocess.Popen`` with a 60-second timeout.

    Args:
        trigger_name: Name of the parent trigger (for result attribution).
        action: Shell action containing the command template.
        ctx: Template interpolation context.

    Returns:
        A :class:`TriggerResult` with ``success=True`` when the process exits
        with code 0.  Captures stdout as ``output`` and stderr as ``error``.
    """
    cmd = _interpolate(action.command, ctx)
    from ..core.types import get_context

    env = os.environ.copy()
    try:
        target_dir = get_context().target_dir
        env["VAULTSPEC_TARGET_DIR"] = str(target_dir)
        if target_dir.is_dir():
            cwd: str | None = str(target_dir)
        else:
            logger.warning(
                "Trigger cwd %s does not exist, using process cwd", target_dir
            )
            cwd = None
    except LookupError:
        cwd = None

    try:
        cmd_args = shlex.split(cmd, posix=(os.name != "nt"))
        process = subprocess.Popen(
            cmd_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            cwd=cwd,
        )
        try:
            stdout, stderr = process.communicate(timeout=60)
        except subprocess.TimeoutExpired:
            kill_process_tree(process.pid)
            process.kill()
            process.communicate()
            logger.warning("Shell trigger '%s' timed out (60s)", trigger_name)
            return TriggerResult(
                trigger_name=trigger_name,
                action_type="shell",
                success=False,
                error="Trigger timed out (60s)",
            )
        return TriggerResult(
            trigger_name=trigger_name,
            action_type="shell",
            success=process.returncode == 0,
            output=stdout.strip(),
            error=stderr.strip(),
        )
    except Exception as e:
        logger.error("Shell trigger '%s' failed: %s", trigger_name, e, exc_info=True)
        return TriggerResult(
            trigger_name=trigger_name,
            action_type="shell",
            success=False,
            error=str(e),
        )


def fire_triggers(
    event: str,
    context: dict[str, str] | None = None,
    *,
    triggers_dir: Path | None = None,
    home: Path | None = None,
) -> None:
    """Fire triggers for a lifecycle event, silently catching all errors.

    This is the lifecycle entry point ``sync`` reaches, so it is the
    highest-traffic route into :func:`trigger`'s consent check. It therefore
    threads ``home`` the same way it threads ``triggers_dir``: without it, the
    consent half of this path could only be exercised against the operator's
    own ledger, and a path that can only be tested destructively is a path
    that does not get tested.

    Args:
        event: Event name to trigger.
        context: Optional context dict passed through to trigger actions.
        home: Machine-global VaultSpec home holding the consent ledger.
            Defaults to the operator's real home, which is what every
            production caller wants; real-filesystem tests pass their own so
            they neither read nor write the operator's approvals.
        triggers_dir: Directory to load trigger definitions from. Defaults to the
            active :func:`~vaultspec_core.core.types.get_context`'s
            ``triggers_dir`` when omitted - the right default for a caller
            operating on a single, ambient workspace. A caller that just
            finished acting on a *different* workspace than the ambient one
            (for example ``sync --target``, which reads its source content
            from the CWD workspace while writing to a separate target) must
            pass the target's own triggers directory explicitly: triggers react to
            an event that happened *to* a workspace, so they must be the
            triggers *that* workspace declares, not whichever happens to be
            ambient when the event fires.
    """
    try:
        if triggers_dir is None:
            from ..core.types import get_context

            triggers_dir = get_context().triggers_dir

        triggers = load_triggers(triggers_dir)
        fire(triggers, event, context, home)
    except Exception:
        logger.warning("Trigger trigger failed for %s", event, exc_info=True)
